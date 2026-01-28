"""Backtest engine for Polymarket weather strategy."""
import logging
import os
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import re

from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.visual_crossing_client import VisualCrossingClient
from agent.tools.trading_strategy import TradingStrategy, TradeSignal

logger = logging.getLogger(__name__)

# Constants
ALLOCATION_PER_TRADE = 100.0

class BacktestEngine:
    """Engine for running historical simulations of the weather strategy."""

    ALLOCATION_PER_TRADE = 100.0

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        weather_client: VisualCrossingClient,
        strategy_params: Optional[Dict[str, Any]] = None
    ):
        """Initialize the backtest engine."""
        self.pm_client = polymarket_client
        self.vc_client = weather_client
        self.strategy = TradingStrategy(**(strategy_params or {}))

    async def run_backtest(
        self,
        city: str,
        target_date: str,
        lookback_days: int = 7,
        is_prediction: bool = False
    ) -> Dict[str, Any]:
        """Run a cross-sectional backtest for a specific city and date range."""
        total_invested = 0
        total_payout = 0
        resolved_invested = 0
        resolved_payout = 0
        pending_invested = 0
        all_results = []
        trades_summary = []
        
        markets_found_total = 0
        markets_processed_total = 0

        # 1. Determine Date Range
        end_dt = datetime.strptime(target_date, "%Y-%m-%d")
        # Or if the user meant "from now on", we interpret target_date usually as "today".
        # Safe bet: shift start back by 1 day.
        
        # If target_date is today, we want backtest to end yesterday.
        # If target_date is already historical, we might keep it.
        # 0. Handle Aliases Globally
        weather_city = city
        if city.upper() in ["NYC", "NYC.", "NEW YORK CITY"]:
            weather_city = "New York"
        elif city.upper() in ["LA", "L.A."]:
            weather_city = "Los Angeles"

        if is_prediction:
            # Prediction: Start from today
            current_dt = datetime.now()
            # Ensure lookback_days is at least 1 for prediction
            count = max(1, lookback_days)
            date_range = [(current_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(count)]
        else:
            # Backtest: End yesterday
            end_dt = datetime.strptime(target_date, "%Y-%m-%d")
            effective_end_dt = end_dt - timedelta(days=1)
            # Ensure lookback_days is at least 1
            count = max(1, lookback_days)
            date_range = [(effective_end_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(count - 1, -1, -1)]
        
        print(f"DEBUG: Mode={'Prediction' if is_prediction else 'Backtest'}, Range={date_range}")

        for current_date in date_range:
            # 2. Discover Market Series
            # Strategy: specific search for "Highest temperature" to cut through noise
            # keys: "Highest temperature in NYC", "Highest temperature in New York"
            # Strategy: Mixed Broad + Specific to ensure maximum recall
            # e.g. "Highest temperature in NYC", "NYC", "New York", "Highest temperature in New York"
            date_obj = datetime.strptime(current_date, "%Y-%m-%d")
            month_name = date_obj.strftime("%B")
            day_num = date_obj.day
            
            queries = {
                f"Highest temperature in {city}", 
                f"Highest temperature in {weather_city}",
                f"{month_name} {day_num} {city} weather",
                f"{month_name} {day_num} {weather_city} weather",
                f"{city} weather",
                f"{weather_city} weather",
                city,
                weather_city
            }
            markets = []
            seen_ids = set()
            print(f"DEBUG: Searching queries: {queries}")
            for q in queries:
                 res = await self.pm_client.gamma_search(q, status="all", limit=500)
                 for m in res:
                     mid = str(m.id)
                     if mid not in seen_ids:
                         markets.append(m)
                         seen_ids.add(mid)
            
            def filter_markets(market_list):
                 date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                 month_name = date_obj.strftime("%B")
                 day_num = date_obj.day
                 date_pattern = f"{month_name} {day_num}"
                 target_year = current_date[:4]  # "2026"
                 
                 filtered = []
                 for m in market_list:
                     if date_pattern not in m.question:
                         continue
                     if "highest temperature" not in m.question.lower():
                         continue
                     # Year Check: m.end_date (ISO "2026-01-26T...") must match current year
                     if m.end_date and not m.end_date.startswith(target_year):
                         continue
                     filtered.append(m)
                     
                 return filtered

            relevant_markets = filter_markets(markets)
            
            # Fallback if nothing found and alias differs
            if not relevant_markets and city.lower() != weather_city.lower():
                alt_query = f"Highest temperature in {weather_city}"
                # Avoid re-running if we already searched this
                if alt_query not in queries:
                     alt_markets = await self.pm_client.gamma_search(alt_query, status="all", limit=500)
                     relevant_markets = filter_markets(alt_markets)

            if not relevant_markets:
                continue

            # Sort markets by temperature threshold
            def get_threshold(q):
                info = self._parse_threshold(q)
                val = info.get("value", 0)
                if "or below" in q.lower(): val -= 0.1
                if "or higher" in q.lower(): val += 0.1
                return val
            relevant_markets.sort(key=lambda x: get_threshold(x.question))

            # Determine if the current date is historical or future
            is_historical = datetime.strptime(current_date, "%Y-%m-%d").date() < datetime.now().date()
            
            actual_weather = None
            weather_error = None

            # Always attempt to fetch weather (handles both historical and forecast)
            try:
                actual_weather = await self.vc_client.get_day_weather(weather_city, current_date)
            except Exception as e:
                print(f"Weather API Error for {current_date}: {e}")
                weather_error = str(e)

            # If we missed weather data for a historical date, we can't probability-check reliably
            if is_historical and not actual_weather:
                if weather_error and "401" in weather_error:
                    # Return partial results found so far + Error
                    return {
                        "city": city,
                        "success": False, 
                        "error": "Visual Crossing API Quota Exceeded (401). Partial results shown.",
                        "trades": all_trades,
                        "markets_found": markets_found_total,
                        "markets_processed": markets_processed_total
                    }
                continue

            # 4. Collect Market Data and Identify Best Entry (Start of Day)
            group_results = []
            prediction_time = datetime.strptime(f"{current_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
            target_ts = int(prediction_time.timestamp())
            resolution_time = datetime.strptime(f"{current_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
            time_left = resolution_time - prediction_time
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_left_str = f"{hours}h {minutes}m"
            
            markets_found_total += len(relevant_markets)

            for market in relevant_markets:
                parsed_threshold = self._parse_threshold(market.question)
                # Skip invalid markets
                if parsed_threshold["value"] == -999: continue
                
                if not actual_weather:
                    continue

                entry_data = {"price": 0.5, "timestamp": "N/A", "fair_price": 0.0, "edge": -1}
                fair_probs = self._calculate_probabilities(actual_weather, market.question)
                fair_price = fair_probs["probability"]

                if market.clob_token_ids:
                    token_id = market.clob_token_ids[0]
                    history = await self.pm_client.get_price_history(token_id)
                    
                    closest = None
                    min_diff = float('inf')
                    for h in history:
                        h_ts = int(h.get("t", h.get("timestamp", 0)))
                        diff = abs(h_ts - target_ts)
                        if diff < min_diff:
                            min_diff = diff
                            closest = h
                    
                    if is_prediction:
                        # Calculate countdown
                        if market.end_date:
                            try:
                                end_dt = datetime.fromisoformat(market.end_date.replace("Z", "+00:00"))
                                now_dt = datetime.now(end_dt.tzinfo)
                                diff = end_dt - now_dt
                                if diff.total_seconds() > 0:
                                    days = diff.days
                                    hours, rem = divmod(diff.seconds, 3600)
                                    mins, _ = divmod(rem, 60)
                                    if days > 0:
                                        countdown = f"{days}d {hours}h"
                                    elif hours > 0:
                                        countdown = f"{hours}h {mins}m"
                                    else:
                                        countdown = f"{mins}m"
                                else:
                                    countdown = "Ended"
                            except:
                                countdown = "N/A"
                        else:
                            countdown = "N/A"
                    else:
                        countdown = "N/A"

                    if closest:
                        price = float(closest.get("p", closest.get("price", 0.5)))
                        if price > 0:
                            entry_data = {
                                "price": price,
                                "timestamp": datetime.fromtimestamp(int(closest.get("t", closest.get("timestamp", 0)))).strftime("%Y-%m-%d %H:%M"),
                                "fair_price": fair_price,
                                "edge": fair_price - price,
                                "countdown": countdown
                            }

                group_results.append({
                    "market": market,
                    "entry_data": entry_data,
                    "fair_price": fair_price
                })

            if not group_results: continue

            # 5. Identify the SINGLE bucket with highest Fair Price
            best_bucket = max(group_results, key=lambda x: x["fair_price"])
            
            # status check
            is_future = datetime.strptime(current_date, "%Y-%m-%d").date() >= datetime.now().date()

            # 4.5 Detect Official Winner in Group (if any)
            official_winner_label = None
            for item in group_results:
                m = item["market"]
                if m.closed and m.yes_price >= 0.99:
                    # This market resolved to YES officially
                    official_winner_label = m.question.split(" be ")[-1].split(" on ")[0]
                    break

            for item in group_results:
                market = item["market"]
                entry_data = item["entry_data"]
                resolution = self._determine_resolution(actual_weather, market.question)
                
                # Use real resolution if market is closed on Polymarket
                is_real_resolution = False
                if market.closed:
                    # For Yes/No markets, if Yes price is 1.0, resolution is 1.0
                    if market.yes_price >= 0.99:
                        resolution = 1.0
                        is_real_resolution = True
                    elif market.yes_price <= 0.01:
                        resolution = 0.0
                        is_real_resolution = True
                
                bucket_label = market.question.split(" be ")[-1].split(" on ")[0]
                
                status = "RESOLVED"
                if is_future:
                    status = "UNRESOLVED/ACTIVE"
                    res_val = "N/A"
                else:
                    res_val = int(resolution)

                threshold_info = self._parse_threshold(market.question)
                creation_ts = market.created_at.replace("Z", "+00:00")
                creation_date_str = datetime.fromisoformat(creation_ts).strftime("%Y-%m-%d %H:%M")

                is_best = (item is best_bucket)
                should_trade = entry_data.get("edge", 0) > 0 and entry_data.get("price", 0) > 0
                
                # Calculate trade metrics
                payout = 0
                pnl = 0
                res_str = "SKIPPED"
                
                if should_trade:
                    if not is_future:
                        shares = self.ALLOCATION_PER_TRADE / entry_data["price"]
                        payout = shares * resolution
                        pnl = payout - self.ALLOCATION_PER_TRADE
                        res_str = "WIN" if resolution > 0.9 else "LOSS"
                        
                        # CRITICAL: Only update GLOBAL totals for the BEST bucket
                        if is_best:
                            total_invested += self.ALLOCATION_PER_TRADE
                            total_payout += payout
                            resolved_invested += self.ALLOCATION_PER_TRADE
                            resolved_payout += payout
                    else:
                        res_str = "PENDING"
                        if is_best:
                            pending_invested += self.ALLOCATION_PER_TRADE
                            total_invested += self.ALLOCATION_PER_TRADE
                
                row_roi = (pnl / self.ALLOCATION_PER_TRADE * 100) if should_trade and not is_future else 0

                all_results.append({
                    "Market ID": market.id,
                    "Market Group": f"Highest temperature in {city} on {current_date}?",
                    "Outcome Bucket": bucket_label,
                    "Status": status,
                    "Market Creation Date": creation_date_str,
                    "Start of Day Date": prediction_time.strftime("%Y-%m-%d %H:%M"),
                    "Market Resolution Date": resolution_time.strftime("%Y-%m-%d %H:%M"),
                    "Forecast Max Temp (F)": round(actual_weather.get("tempmax", 0), 1), 
                    "Forecast Update Time": actual_weather.get("forecast_time", "N/A"),
                    "Actual Max Temp (F)": round(actual_weather["tempmax"], 1) if not is_future else "PENDING",
                    "Target Fahrenheit": round(threshold_info.get("value"), 1),
                    "Predicted Probability": f"{int(item['fair_price'] * 100)}% ({round(item['fair_price'], 2)})",
                    "Best Entry Price": round(entry_data["price"], 3),
                    "Ends In": entry_data.get("countdown", "N/A"),
                    "Entry Time": entry_data["timestamp"],
                    "Resolution": res_val,
                    "Resolution Source": "OFFICIAL" if is_real_resolution else "SIMULATED",
                    "Time Till Resolution": time_left_str,
                    "Invested ($)": self.ALLOCATION_PER_TRADE if should_trade and is_best else 0,
                    "Payout ($)": round(payout, 2) if should_trade else "N/A",
                    "PnL ($)": round(pnl, 2) if should_trade else "N/A",
                    "ROI (%)": f"{row_roi:.1f}%" if should_trade and not is_future else "N/A",
                    "Is Recommendation": "YES" if is_best else "NO"
                })

                if is_best:
                    # Default to simulated weather
                    raw_actual = actual_weather["tempmax"]
                    actual_display = f"{round(raw_actual, 1)}°F"
                    
                    if threshold_info.get("original_unit") == "C":
                        c_val = (raw_actual - 32) * 5/9
                        actual_display = f"{round(c_val, 1)}°C ({round(raw_actual, 1)}°F)"

                    # If official winner exists, OVERRIDE with that value
                    if official_winner_label:
                        # Find the winning market object to parse its threshold
                        win_m = next((i["market"] for i in group_results if i["market"].question.split(" be ")[-1].split(" on ")[0] == official_winner_label), None)
                        # Fallback search if label matching was inexact
                        if not win_m:
                             win_m = next((i["market"] for i in group_results if i["market"].closed and i["market"].yes_price >= 0.99), None)
                        
                        if win_m:
                            win_info = self._parse_threshold(win_m.question)
                            if win_info.get("original_unit") == "C":
                                w_c = win_info["original"]
                                w_f = win_info["value"]
                                actual_display = f"{w_c}°C ({round(w_f, 1)}°F)"
                            else:
                                w_f = win_info["value"]
                                actual_display = f"{round(w_f, 1)}°F"
                            
                            # Add small marker
                            actual_display += "*"

                    trades_summary.append({
                        "date": current_date,
                        "market_id": market.id,
                        "market_name": market.question,
                        "bucket": bucket_label,
                        "target_f": round(threshold_info.get("value"), 0), # Added for compatibility
                        "target_display": f"{bucket_label} ({round(threshold_info.get('value'), 1)}°F)",
                        "forecast": round(actual_weather.get("tempmax", 0), 1),
                        "forecast_time": actual_weather.get("forecast_time", "N/A"),
                        "actual": actual_display,
                        "prob": f"{int(item['fair_price'] * 100)}%",
                        "market_prob": f"{int(entry_data['price'] * 100)}%",
                        "price": round(entry_data["price"], 3),
                        "countdown": entry_data.get("countdown", "N/A"),
                        "result": res_str
                    })

        # 6. Save and Return Summary
        os.makedirs("test-results", exist_ok=True)
        file_type = "prediction" if is_prediction else "backtest"
        csv_file = f"test-results/{city}_{file_type}_{target_date}_lb{lookback_days}.csv"
        
        final_pnl = total_payout - total_invested
        total_roi = (final_pnl / total_invested * 100) if total_invested > 0 else 0
        resolved_roi = ((resolved_payout - resolved_invested) / resolved_invested * 100) if resolved_invested > 0 else 0

        if all_results:
            summary_row = {k: "" for k in all_results[0].keys()}
            summary_row["Market Group"] = "TOTAL SUMMARY"
            summary_row["Invested ($)"] = round(total_invested, 2)
            summary_row["Payout ($)"] = round(total_payout, 2)
            summary_row["PnL ($)"] = round(final_pnl, 2)
            summary_row["ROI (%)"] = round(total_roi, 2)
            all_results.append(summary_row)

            with open(csv_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
                writer.writeheader()
                writer.writerows(all_results)

        return {
            "success": True,
            "city": city,
            "period": f"{date_range[0]} to {date_range[-1]}",
            "total_invested": total_invested,
            "total_payout": total_payout,
            "resolved_invested": resolved_invested,
            "resolved_payout": resolved_payout,
            "resolved_roi": resolved_roi,
            "pending_invested": pending_invested,
            "final_pnl": final_pnl,
            "final_roi": total_roi,
            "csv_path": csv_file,
            "trades": trades_summary,
            "markets_found": markets_found_total,
            "markets_processed": markets_processed_total
        }

    def _parse_threshold(self, question: str) -> Dict[str, Any]:
        """Extract temperature threshold and unit from question."""
        # Check for ranges first (e.g. "14-15°F", "between 10 and 20")
        # Regex for "number - number" where the hyphen is NOT a negative sign for the second number
        # We capture two numbers.
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-to]\s*(\d+(?:\.\d+)?)", question)
        if range_match:
             val1 = float(range_match.group(1))
             val2 = float(range_match.group(2))
             # Determine unit usually at the end
             unit_match = re.search(r"[0-9]\s*°?([CF])", question, re.IGNORECASE)
             unit = unit_match.group(1).upper() if unit_match else "F"
             
             avg_val = (val1 + val2) / 2
             if unit == 'C':
                return {"value": (avg_val * 9/5) + 32, "unit": "F"}
             return {"value": avg_val, "unit": "F"}

        # Standard single value regex
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?([CF])", question, re.IGNORECASE)
        if not match:
             # Fallback for just a number
             match = re.search(r"(-?\d+(?:\.\d+)?)", question)
             if not match: return {"value": 0.0, "unit": "F"}
             return {"value": float(match.group(1)), "unit": "F"}
        
        val = float(match.group(1))
        unit = match.group(2).upper()
        if unit == 'C':
            f_val = (val * 9/5) + 32
            return {"value": f_val, "unit": "F", "original": val, "original_unit": "C"}
        return {"value": val, "unit": "F"}

    def _calculate_probabilities(self, weather: Dict[str, Any], question: str) -> Dict[str, float]:
        """Heuristic for fair price based on observed weather."""
        threshold_info = self._parse_threshold(question)
        target_val = threshold_info["value"] 
        actual_val = weather.get("tempmax", 0) 
        diff = actual_val - target_val
        
        is_above = "or higher" in question.lower() or "exceed" in question.lower() or "above" in question.lower()
        is_below = "or below" in question.lower() or "below" in question.lower() or "less than" in question.lower()
        is_discrete = not (is_above or is_below)

        if is_discrete:
            abs_diff = abs(diff)
            if abs_diff < 1.0: prob = 0.95
            elif abs_diff < 2.0: prob = 0.70
            elif abs_diff < 3.0: prob = 0.30
            else: prob = 0.05
        elif is_below:
            if diff < -2.0: prob = 0.95
            elif diff > 2.0: prob = 0.05
            else: prob = 0.5 - (diff / 4.0)
        else: # is_above
            if diff > 2.0: prob = 0.95
            elif diff < -2.0: prob = 0.05
            else: prob = 0.5 + (diff / 4.0)

        return {"probability": prob, "threshold_f": target_val, "actual_f": actual_val}

    def _determine_resolution(self, weather: Dict[str, Any], question: str) -> float:
        """Determine if the YES token resolved to 1.0 or 0.0."""
        threshold_info = self._parse_threshold(question)
        target_f = threshold_info["value"]
        actual_f = weather.get("tempmax", 0)
        
        is_above = "or higher" in question.lower() or "exceed" in question.lower() or "above" in question.lower()
        is_below = "or below" in question.lower() or "below" in question.lower() or "less than" in question.lower()
        is_discrete = not (is_above or is_below)
        
        if is_discrete:
            return 1.0 if abs(actual_f - target_f) < 1.1 else 0.0
        elif is_below:
            return 1.0 if actual_f <= (target_f + 0.1) else 0.0
        else: # is_above
            return 1.0 if actual_f >= (target_f - 0.1) else 0.0
