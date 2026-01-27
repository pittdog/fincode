#!/usr/bin/env python3
"""Backtest CLI for Polymarket trading strategy."""
import asyncio
import sys
from pathlib import Path
from utils.polymarket_backtest_util import run_backtest_analysis


async def main():
    """Run backtest analysis."""
    print("\n" + "=" * 70)
    print("POLYMARKET TRADING STRATEGY - BACKTEST ANALYSIS")
    print("=" * 70 + "\n")
    
    # Configuration
    num_markets = 150
    num_weather_points = 150
    days = 30
    initial_capital = 197.0
    
    print(f"Configuration:")
    print(f"  Markets to analyze:     {num_markets}")
    print(f"  Weather data points:    {num_weather_points}")
    print(f"  Backtest period:        {days} days")
    print(f"  Initial capital:        ${initial_capital:.2f}")
    print()
    
    try:
        results = await run_backtest_analysis(
            num_markets=num_markets,
            num_weather_points=num_weather_points,
            days=days,
            initial_capital=initial_capital,
            output_dir="test-results",
        )
        
        print("\n" + "=" * 70)
        print("Backtest completed successfully!")
        print("=" * 70)
        
        return 0
    except Exception as e:
        print(f"\nError during backtest: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
