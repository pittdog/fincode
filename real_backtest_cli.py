#!/usr/bin/env python3
"""Real backtest CLI using actual API data from Polymarket and Tomorrow.io."""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

from utils.real_backtest_util import run_real_backtest


async def main():
    """Run real backtest with API data."""
    # Load environment
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    print("\n" + "=" * 70)
    print("POLYMARKET REAL DATA BACKTEST")
    print("=" * 70 + "\n")
    
    # Get API keys
    tomorrow_io_key = os.getenv("TOMORROWIO_API_KEY")
    polymarket_key = os.getenv("POLYMARKET_API_KEY")
    
    if not tomorrow_io_key:
        print("Error: TOMORROWIO_API_KEY environment variable not set")
        print("Please set it in .env file or environment")
        return 1
    
    print("Configuration:")
    print(f"  Tomorrow.io API:        {'✓ Configured' if tomorrow_io_key else '✗ Missing'}")
    print(f"  Polymarket API:         {'✓ Configured' if polymarket_key else '✗ Optional'}")
    print(f"  Initial Capital:        $197.00")
    print(f"  Capital per Trade:      $50.00")
    print()
    
    try:
        results = await run_real_backtest(
            tomorrow_io_key=tomorrow_io_key,
            polymarket_api_key=polymarket_key,
            output_dir="test-results",
        )
        
        if results:
            print("\n" + "=" * 70)
            print("Real backtest completed successfully!")
            print("=" * 70)
            return 0
        else:
            print("\n" + "=" * 70)
            print("No data available for backtest")
            print("=" * 70)
            return 1
    
    except Exception as e:
        print(f"\nError during backtest: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
