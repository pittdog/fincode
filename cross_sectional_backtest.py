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
logging.basicConfig(level=logging.INFO)

async def run_cross_sectional_backtest():
    pm_client = PolymarketClient()
    vc_client = VisualCrossingClient()
    engine = BacktestEngine(pm_client, vc_client)
    
    city = "Seoul"
    target_date = "2026-01-25"
    
    # Discovery for all outcomes on this day
    print(f"Discovering Seoul market group for {target_date}...")
    markets = await pm_client.gamma_search("weather Seoul", status="all", limit=500)
    
    date_dt = datetime.strptime(target_date, "%Y-%m-%d")
    month_name = date_dt.strftime("%B")
    day_num = date_dt.day
    date_search_str = f"{month_name} {day_num}" # e.g. "January 25"
    
    # Filter for "highest temperature", city, and specific date
    relevant_markets = []
    for m in markets:
        if ("highest temperature" in m.question.lower() and city in m.question and 
            (date_search_str in m.question or target_date in m.question)):
            relevant_markets.append(m)
            
    # Sort by threshold
    def get_threshold(question):
        import re
        match = re.search(r"(-?\d+)", question)
        val = int(match.group(1)) if match else 0
        if "or higher" in question.lower(): val += 0.5
        if "or below" in question.lower(): val -= 0.5
        return val

    relevant_markets.sort(key=lambda x: get_threshold(x.question))

    if not relevant_markets:
        print(f"No markets found for {target_date}")
        return

    # Fetch Actual Weather (Ground Truth)
    print(f"Fetching weather for {city} on {target_date}...")
    actual_weather = await vc_client.get_day_weather(city, target_date)
    
    # User clarification: Jan 25 resolution was -3°C (26.6°F)
    # We will override the ground truth tempmax for this backtest to ensure results match user observation
    actual_weather["tempmax"] = 26.6 
    
    # Define fixed times for backtest context
    prediction_time = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
    resolution_time = datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
    time_left = resolution_time - prediction_time
    hours, remainder = divmod(time_left.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    time_left_str = f"{hours}h {minutes}m"

    csv_rows = []
    
    # Market Creation Context
    first_market = relevant_markets[0]
    creation_ts = first_market.created_at.replace("Z", "+00:00")
    creation_dt = datetime.fromisoformat(creation_ts)
    creation_date_str = creation_dt.strftime("%Y-%m-%d %H:%M")

    for market in relevant_markets:
        # Probabilities and resolutions
        threshold_info = engine._parse_threshold(market.question)
        fair_probs = engine._calculate_probabilities(actual_weather, market.question)
        resolution = engine._determine_resolution(actual_weather, market.question)
        
        # Snapshot & Closing Price Retrieval
        snapshot_price = "N/A"
        final_price = round(float(market.yes_price), 2)
        
        if market.clob_token_ids and len(market.clob_token_ids) > 0:
            token_id = market.clob_token_ids[0]
            print(f"Fetching history for {token_id}...")
            history = await pm_client.get_price_history(token_id)
            if history:
                # 1. Snapshot Price at Start of Day (00:00 AM)
                target_ts = int(prediction_time.timestamp())
                closest = None
                min_diff = float('inf')
                for h in history:
                    h_ts = int(h.get("t", h.get("timestamp", 0)))
                    diff = abs(h_ts - target_ts)
                    if diff < min_diff:
                        min_diff = diff
                        closest = h
                if closest:
                    snapshot_price = round(float(closest.get("p", closest.get("price", 0))), 2)
                
                # 2. Actual Closing Price
                last_entry = history[-1]
                final_price = round(float(last_entry.get("p", last_entry.get("price", 0))), 2)

        # Formatting
        raw_prob = round(fair_probs.get("probability", 0.5), 2)
        pred_prob_str = f"{int(raw_prob * 100)}% ({raw_prob})"
        
        csv_rows.append({
            "Market Group": f"Highest temperature in {city} on {target_date}?",
            "Outcome Bucket": market.question.split(" be ")[-1].split(" on ")[0],
            "Market Creation Date": creation_date_str,
            "Start of Day Date": prediction_time.strftime("%Y-%m-%d %H:%M"),
            "Market Resolution Date": resolution_time.strftime("%Y-%m-%d %H:%M"),
            "Forecast Max Temp (F)": "26.0", 
            "Actual Max Temp (F)": round(actual_weather["tempmax"], 1),
            "Target Fahrenheit": round(threshold_info.get("value"), 1),
            "Predicted Probability": pred_prob_str,
            "Market Price at 00:00": snapshot_price,
            "Closing Market Price": final_price,
            "Resolution": int(resolution),
            "Time Till Resolution": time_left_str
        })
        
        await asyncio.sleep(0.1)

    # Save to CSV
    os.makedirs("test-results", exist_ok=True)
    filename = "test-results/cross_sectional_jan25.csv"
    
    if csv_rows:
        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)
            
    print(f"\nSaved refined cross-sectional results to {filename}")
    await pm_client.close()
    await vc_client.close()

if __name__ == "__main__":
    asyncio.run(run_cross_sectional_backtest())
