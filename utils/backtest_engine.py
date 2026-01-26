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
        lookback_days: int = 7
    ) -> Dict[str, Any]:
        """Run a cross-sectional backtest for a specific city and date range."""
        total_invested = 0
        total_payout = 0
        resolved_invested = 0
        resolved_payout = 0
        pending_invested = 0
        all_results = []
        trades_summary = []

        # 1. Determine Date Range
        end_dt = datetime.strptime(target_date, "%Y-%m-%d")
        date_range = [(end_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(lookback_days, -1, -1)]

        for current_date in date_range:
            # 2. Discover Market Series
            search_query = f"weather {city}"
            markets = await self.pm_client.gamma_search(search_query, status="all")
            
            # Filter for specific date in question
            date_obj = datetime.strptime(current_date, "%Y-%m-%d")
            month_name = date_obj.strftime("%B")
            day_num = date_obj.day
            date_pattern = f"{month_name} {day_num}"
            
            relevant_markets = [
                m for m in markets 
                if date_pattern in m.question 
                and "highest temperature" in m.question.lower()
            ]

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

            # 3. Fetch Actual Weather
            try:
                actual_weather = await self.vc_client.get_day_weather(city, current_date)
            except Exception:
                continue
            
            if not actual_weather:
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

            for market in relevant_markets:
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
                    
                    if closest:
                        price = float(closest.get("p", closest.get("price", 0.5)))
                        if price > 0:
                            entry_data = {
                                "price": price,
                                "timestamp": datetime.fromtimestamp(int(closest.get("t", closest.get("timestamp", 0)))).strftime("%Y-%m-%d %H:%M"),
                                "fair_price": fair_price,
                                "edge": fair_price - price
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

            for item in group_results:
                market = item["market"]
                entry_data = item["entry_data"]
                resolution = self._determine_resolution(actual_weather, market.question)
                bucket_label = market.question.split(" be ")[-1].split(" on ")[0]
                
                status = "RESOLVED"
                if is_future:
                    status = "UNRESOLVED/ACTIVE"
                    payout = 0
                    pnl = 0
                    res_val = "N/A"
                else:
                    res_val = int(resolution)

                threshold_info = self._parse_threshold(market.question)
                creation_ts = market.created_at.replace("Z", "+00:00")
                creation_date_str = datetime.fromisoformat(creation_ts).strftime("%Y-%m-%d %H:%M")

                is_best = (item == best_bucket)
                should_trade = is_best and entry_data.get("edge", 0) > 0 and entry_data.get("price", 0) > 0
                
                if should_trade:
                    if not is_future:
                        shares = self.ALLOCATION_PER_TRADE / entry_data["price"]
                        payout = shares * resolution
                        pnl = payout - self.ALLOCATION_PER_TRADE
                        total_invested += self.ALLOCATION_PER_TRADE
                        total_payout += payout
                        resolved_invested += self.ALLOCATION_PER_TRADE
                        resolved_payout += payout
                        res_str = "WIN" if resolution > 0 else "LOSS"
                    else:
                        pending_invested += self.ALLOCATION_PER_TRADE
                        pnl = 0
                        payout = 0
                        res_str = "PENDING"
                    
                    trades_summary.append({
                        "date": current_date,
                        "market_name": market.question,
                        "bucket": bucket_label,
                        "target_f": round(threshold_info.get("value", 0), 1),
                        "forecast": round(actual_weather.get("tempmax", 0), 1),
                        "actual": round(actual_weather["tempmax"], 1) if not is_future else "PENDING",
                        "prob": f"{int(item['fair_price'] * 100)}%",
                        "price": round(entry_data["price"], 3),
                        "result": res_str
                    })
                else:
                    pnl = 0
                    payout = 0

                row_roi = (pnl / self.ALLOCATION_PER_TRADE * 100) if should_trade and not is_future else 0
                
                all_results.append({
                    "Market Group": f"Highest temperature in {city} on {current_date}?",
                    "Outcome Bucket": bucket_label,
                    "Status": status,
                    "Market Creation Date": creation_date_str,
                    "Start of Day Date": prediction_time.strftime("%Y-%m-%d %H:%M"),
                    "Market Resolution Date": resolution_time.strftime("%Y-%m-%d %H:%M"),
                    "Forecast Max Temp (F)": round(actual_weather.get("tempmax", 0), 1), 
                    "Actual Max Temp (F)": round(actual_weather["tempmax"], 1) if not is_future else "PENDING",
                    "Target Fahrenheit": round(threshold_info.get("value"), 1),
                    "Predicted Probability": f"{int(item['fair_price'] * 100)}% ({round(item['fair_price'], 2)})",
                    "Best Entry Price": round(entry_data["price"], 3),
                    "Entry Time": entry_data["timestamp"],
                    "Resolution": res_val,
                    "Time Till Resolution": time_left_str,
                    "Invested ($)": self.ALLOCATION_PER_TRADE if should_trade else 0,
                    "Payout ($)": round(payout, 2) if status == "RESOLVED" else "N/A",
                    "PnL ($)": round(pnl, 2) if status == "RESOLVED" else "N/A",
                    "ROI (%)": round(row_roi, 2) if status == "RESOLVED" else "N/A"
                })

        # 6. Save and Return Summary
        os.makedirs("test-results", exist_ok=True)
        csv_file = f"test-results/{city}_backtest_{target_date}_lb{lookback_days}.csv"
        
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
            "trades": trades_summary
        }

    def _parse_threshold(self, question: str) -> Dict[str, Any]:
        """Extract temperature threshold and unit from question."""
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?([CF])", question, re.IGNORECASE)
        if not match:
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
