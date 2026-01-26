import asyncio
import json
import csv
from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.visual_crossing_client import VisualCrossingClient
from utils.backtest_engine import BacktestEngine
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)

async def run_matched_series_backtests():
    pm_client = PolymarketClient()
    vc_client = VisualCrossingClient()
    engine = BacktestEngine(pm_client, vc_client)
    
    city = "Seoul"
    
    # Matched markets for Seoul -2°C Series (based on discovery)
    # This is exactly one series (-2C) for previous days as requested.
    targets = [
        {"market_id": "1219271", "date": "2026-01-21"}, # -2C or higher
        {"market_id": "1226728", "date": "2026-01-22"}, # -2C
        {"market_id": "1233838", "date": "2026-01-23"}, # -2C
        {"market_id": "1240923", "date": "2026-01-24"}, # -2C 
        {"market_id": "1248361", "date": "2026-01-25"}, # -2C
        {"market_id": "1257519", "date": "2026-01-26"}, # -2C
        {"market_id": "1264823", "date": "2026-01-27"}  # -2C
    ]
    
    csv_rows = []
    all_results = []
    
    # NO PRE-FETCH BATCH (to avoid triggering aggressive 429)
    # We will process each market one by one with a generous sleep.
    
    for t in targets:
        market_id = t["market_id"]
        date = t["date"]
        
        print(f"\nProcessing market {market_id} for {date}...")
        
        try:
            # We use lookback_days=0 to minimize weather API calls to just the resolution day.
            # This should be safer for rate limits.
            res = await engine.run_backtest(city, date, market_id=market_id, lookback_days=0)
            
            if res.get("success"):
                all_results.append(res)
                for step in res.get("simulation", []):
                    csv_rows.append({
                        "market_id": market_id,
                        "city": city,
                        "question": res.get("question"),
                        "target_c": step.get("original_threshold_c"),
                        "target_f": step.get("target_threshold_f"),
                        "resolution_date": date,
                        "timestamp": step["time"],
                        "market_price": step["market_price"],
                        "fair_price": step["fair_price"],
                        "edge": step["edge"],
                        "signal": step["signal"],
                        "checkpoint_temp_f": step["actual_temp_checkpoint"],
                        "actual_day_max_f": step.get("actual_day_max_temp"),
                        "forecast_day_max_f": step.get("forecast_day_max_temp"),
                        "actual_resolution": step["target_resolution"]
                    })
            else:
                print(f"Backtest failed for {date}: {res.get('error')}")
            
            # MANDATORY SLEEP between markets to stay under rate limits
            print("Sleeping 1 second to respect rate limits...")
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error for {date}: {e}")

    # Save Results
    os.makedirs("test-results", exist_ok=True)
    
    # Save JSON
    with open("test-results/real_backtest_data.json", "w") as f:
        json.dump(all_results, f, indent=2)
        
    # Save CSV
    if csv_rows:
        with open("test-results/real_backtest_data.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)
            
    print(f"\nSaved {len(all_results)} backtests to test-results/")
    await pm_client.close()
    await vc_client.close()

if __name__ == "__main__":
    asyncio.run(run_matched_series_backtests())
