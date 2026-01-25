#!/usr/bin/env python3
"""CLI for running real backtest with detailed trade tracking."""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.real_backtest_with_trades import run_real_backtest_with_trades


async def main():
    """Main entry point."""
    # Get API keys from environment
    tomorrow_io_key = os.getenv("TOMORROWIO_API_KEY")
    polymarket_key = os.getenv("POLYMARKET_API_KEY")
    
    if not tomorrow_io_key:
        print("❌ Error: TOMORROWIO_API_KEY environment variable not set")
        print("\nPlease set the API key:")
        print("  export TOMORROWIO_API_KEY=your_key_here")
        print("\nOr create a .env file with:")
        print("  TOMORROWIO_API_KEY=your_key_here")
        sys.exit(1)
    
    print("=" * 70)
    print("POLYMARKET REAL DATA BACKTEST WITH TRADE TRACKING")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  Tomorrow.io API:        ✓ Configured")
    print(f"  Polymarket API:         {'✓ Configured' if polymarket_key else '✗ Optional'}")
    print(f"  Initial Capital:        $197.00")
    print(f"  Capital per Trade:      $50.00")
    print("=" * 70)
    
    # Run backtest
    results = await run_real_backtest_with_trades(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=polymarket_key,
        output_dir="test-results",
    )
    
    if results:
        print("\n✅ Backtest completed successfully!")
        print(f"Results saved to test-results/")
    else:
        print("\n⚠️  Backtest completed with no trades executed")


if __name__ == "__main__":
    asyncio.run(main())
