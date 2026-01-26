import asyncio
import json
import csv
from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.visual_crossing_client import VisualCrossingClient
from utils.backtest_engine import BacktestEngine
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

import logging
import argparse
from datetime import timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_cross_sectional_backtest(city: str, target_date: str, lookback_days: int):
    pm_client = PolymarketClient()
    vc_client = VisualCrossingClient()
    engine = BacktestEngine(pm_client, vc_client)
    
    # Starting Bankroll & Trade Allocation
    INITIAL_BANKROLL = 1000.0
    ALLOCATION_PER_TRADE = 100.0 # 10% of initial
    
    print(f"\n🚀 Running Backtest for {city} | End Date: {target_date} | Lookback: {lookback_days} days")
    print(f"💰 Starting Bankroll: ${INITIAL_BANKROLL} | Allocation: ${ALLOCATION_PER_TRADE}/trade\n")

    # Calculate date range
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    date_range = [(target_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(lookback_days + 1)]
    date_range.reverse() # Start to End

    all_results = []
    total_invested = 0
    total_payout = 0

    for current_date in date_range:
        print(f"--- Processing {current_date} ---")
        
        # Discovery for all outcomes on this day
        markets = await pm_client.gamma_search(f"weather {city}", status="all", limit=500)
        
        date_dt = datetime.strptime(current_date, "%Y-%m-%d")
        month_name = date_dt.strftime("%B")
        day_num = date_dt.day
        date_search_str = f"{month_name} {day_num}" # e.g. "January 25"
        
        # Filter for "highest temperature", city, and specific date
        relevant_markets = []
        for m in markets:
            if ("highest temperature" in m.question.lower() and city in m.question and 
                (date_search_str in m.question or current_date in m.question)):
                relevant_markets.append(m)
        
        if not relevant_markets:
            print(f"No markets found for {current_date}")
            continue

        # Sort by threshold
        def get_threshold(question):
            import re
            match = re.search(r"(-?\d+)", question)
            val = int(match.group(1)) if match else 0
            if "or higher" in question.lower(): val += 0.5
            if "or below" in question.lower(): val -= 0.5
            return val
        relevant_markets.sort(key=lambda x: get_threshold(x.question))

        # Fetch Actual Weather
        try:
            actual_weather = await vc_client.get_day_weather(city, current_date)
        except Exception as e:
            print(f"Weather API failed for {city} on {current_date}: {e}")
            continue
        
        if not actual_weather:
            print(f"Could not get weather for {current_date}")
            continue

        # Collect data for all markets in the group first
        group_results = []
        prediction_time = datetime.strptime(f"{current_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        target_ts = int(prediction_time.timestamp())

        for market in relevant_markets:
            # Revert to "Snapshot Price at 00:00 AM" for entry
            entry_data = {"price": 0.5, "timestamp": "N/A", "fair_price": 0.0}
            
            fair_probs = engine._calculate_probabilities(actual_weather, market.question)
            fair_price = fair_probs["probability"]

            if market.clob_token_ids:
                token_id = market.clob_token_ids[0]
                history = await pm_client.get_price_history(token_id)
                
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
                    entry_data = {
                        "price": price,
                        "timestamp": datetime.fromtimestamp(int(closest.get("t", closest.get("timestamp", 0)))).strftime("%Y-%m-%d %H:%M"),
                        "fair_price": fair_price,
                        "edge": fair_price - price
                    }

            resolution = engine._determine_resolution(actual_weather, market.question)
            group_results.append({
                "market": market,
                "entry_data": entry_data,
                "resolution": resolution,
                "fair_price": fair_price
            })

        # Identify the SINGLE bucket with the highest Fair Price (highest estimation)
        best_bucket = max(group_results, key=lambda x: x["fair_price"])
        
        # Define fixed times for backtest context
        
        # Define fixed times for backtest context
        prediction_time = datetime.strptime(f"{current_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        resolution_time = datetime.strptime(f"{current_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
        time_left = resolution_time - prediction_time
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        time_left_str = f"{hours}h {minutes}m"
        for item in group_results:
            market = item["market"]
            entry_data = item["entry_data"]

            # Determine Resolution Status
            is_future = datetime.strptime(current_date, "%Y-%m-%d").date() >= datetime.now().date()
            resolution = engine._determine_resolution(actual_weather, market.question)
            
            status = "RESOLVED"
            if is_future:
                status = "UNRESOLVED/ACTIVE"
                # For unresolved, we can't settle PnL yet
                payout = 0
                pnl = 0
                res_val = "N/A"
            else:
                res_val = int(resolution)

            threshold_info = engine._parse_threshold(market.question)
            
            # Market Creation Context
            creation_ts = market.created_at.replace("Z", "+00:00")
            creation_dt = datetime.fromisoformat(creation_ts)
            creation_date_str = creation_dt.strftime("%Y-%m-%d %H:%M")

            # SIMULATE TRADE: Only if this is the best bucket AND has edge > 0
            is_best = (item == best_bucket)
            should_trade = is_best and entry_data.get("edge", 0) > 0 and entry_data.get("price", 0) > 0
            
            if should_trade and not is_future:
                shares = ALLOCATION_PER_TRADE / entry_data["price"]
                payout = shares * resolution
                pnl = payout - ALLOCATION_PER_TRADE
                
                total_invested += ALLOCATION_PER_TRADE
                total_payout += payout
                
                res_str = "WIN" if resolution > 0 else "LOSS"
                target_f = round(threshold_info.get("value"), 1)
                actual_f = round(actual_weather["tempmax"], 1)
                print(f"🎯 TRADING Best Bucket: {market.question}")
                print(f"   Price: {round(entry_data['price'],3)} | Fair: {round(item['fair_price'],2)}")
                print(f"   Target: {target_f}°F | Actual: {actual_f}°F | Result: {res_str}")
            elif should_trade and is_future:
                # Still record the investment but don't count payout yet
                total_invested += ALLOCATION_PER_TRADE
                pnl = 0
                payout = 0
                print(f"⏳ TRADING Best Bucket (ACTIVE): {market.question}")
                print(f"   Entry: {round(entry_data['price'],3)} | Fair: {round(item['fair_price'],2)} | Status: {status}")
            else:
                pnl = 0
                shares = 0
                payout = 0

            # Combined Column Structure
            row_roi = (pnl / ALLOCATION_PER_TRADE * 100) if should_trade and not is_future and ALLOCATION_PER_TRADE > 0 else 0
            all_results.append({
                "Market Group": f"Highest temperature in {city} on {current_date}?",
                "Outcome Bucket": market.question.split(" be ")[-1].split(" on ")[0],
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
                "Invested ($)": ALLOCATION_PER_TRADE if should_trade else 0,
                "Payout ($)": round(payout, 2) if status == "RESOLVED" else "N/A",
                "PnL ($)": round(pnl, 2) if status == "RESOLVED" else "N/A",
                "ROI (%)": round(row_roi, 2) if status == "RESOLVED" else "N/A"
            })

    # Save to CSV
    os.makedirs("test-results", exist_ok=True)
    csv_file = f"test-results/{city}_backtest_{target_date}_lb{lookback_days}.csv"
    
    if all_results:
        # Summary Statistics
        final_pnl = total_payout - total_invested
        total_roi = (final_pnl / total_invested * 100) if total_invested > 0 else 0

        # Append Summary Row
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
            
        print(f"\n--- Backtest Summary: {city} ---")
        print(f"Period: {date_range[0]} to {date_range[-1]}")
        print(f"Total Invested: ${round(total_invested, 2)}")
        print(f"Total Payout:   ${round(total_payout, 2)}")
        print(f"Final PnL:      ${round(final_pnl, 2)}")
        print(f"Final ROI:      {round(total_roi, 2)}%")
        print(f"Results saved to: {csv_file}")

    await pm_client.close()
    await vc_client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Cross-Sectional Backtest")
    parser.add_argument("--city", type=str, default="Seoul", help="City name")
    parser.add_argument("--target-date", type=str, default="2026-01-25", help="Target end date (YYYY-MM-DD)")
    parser.add_argument("--lookback", type=int, default=0, help="Number of days to look back")
    
    args = parser.parse_args()
    asyncio.run(run_cross_sectional_backtest(args.city, args.target_date, args.lookback))
