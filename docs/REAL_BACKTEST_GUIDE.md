# Real Historical Data Backtesting Guide

## Overview

This guide explains how to run backtests using **actual historical data** from Polymarket and Tomorrow.io APIs instead of synthetic data.

## Architecture

### Three-Tier Testing Approach

```
┌─────────────────────────────────────────────────────────────┐
│  Unit Tests (Mocked)                                        │
│  - tests/test_polyagent.py (21 tests)                       │
│  - Fast, isolated component testing                          │
│  - No external API calls                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Synthetic Backtest Tests                                   │
│  - tests/backtests/test_backtest_engine.py (16 tests)      │
│  - Generated historical data                                 │
│  - Tests backtest infrastructure                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Real Data Backtest Tests                                   │
│  - tests/backtests/test_real_backtest.py (13 tests)        │
│  - Actual API data structures                                │
│  - Real market and weather data                              │
│  - Production-ready validation                               │
└─────────────────────────────────────────────────────────────┘
```

## Real Data Components

### 1. Real Historical Data Fetcher

**File:** `utils/real_historical_data.py`

Fetches actual data from two APIs:

#### Polymarket Gamma API
- **Endpoint:** `https://gamma-api.polymarket.com/markets`
- **Data:** Live market prices, liquidity, volume
- **Cities:** Automatically extracts from market questions
- **Free:** Yes, no authentication required

```python
from utils.real_historical_data import RealHistoricalDataFetcher

fetcher = RealHistoricalDataFetcher(tomorrow_io_key="YOUR_KEY")
markets = await fetcher.fetch_polymarket_weather_markets(
    search_query="weather",
    limit=100
)
```

#### Tomorrow.io Weather API
- **Endpoint:** `https://api.tomorrow.io/v4/weather/forecast`
- **Data:** Temperature, weather conditions, forecasts
- **Cities:** London, New York, Seoul, Tokyo, Paris
- **Free:** Yes, with API key

```python
weather_data = await fetcher.fetch_all_cities_weather(
    cities=["London", "New York", "Seoul"]
)
```

### 2. Real Backtest Engine

**File:** `utils/real_backtest_util.py`

Runs backtests on actual market and weather data:

```python
from utils.real_backtest_util import RealBacktestEngine

engine = RealBacktestEngine()
results = engine.run_backtest(
    market_data=markets,
    weather_data=weather_data,
    initial_capital=197.0,
    capital_per_trade=50.0
)
```

### 3. CLI Tools

#### Real Backtest CLI
```bash
python3 real_backtest_cli.py
```

Requires `.env` file with:
```
TOMORROWIO_API_KEY=your_key_here
POLYMARKET_API_KEY=optional
```

## Data Structures

### RealHistoricalMarketData

```python
@dataclass
class RealHistoricalMarketData:
    timestamp: str                    # ISO format timestamp
    market_id: str                    # Polymarket market ID
    city: str                         # Extracted city name
    question: str                     # Market question
    yes_price: float                  # Current YES token price
    no_price: float                   # Current NO token price
    liquidity: float                  # Market liquidity in dollars
    volume: float                     # 24h trading volume
    outcomes: List[str]               # ["Yes", "No"]
```

### RealHistoricalWeatherData

```python
@dataclass
class RealHistoricalWeatherData:
    timestamp: str                    # ISO format timestamp
    city: str                         # City name
    latitude: float                   # City latitude
    longitude: float                  # City longitude
    high_temp: float                  # High temperature (°C)
    low_temp: float                   # Low temperature (°C)
    avg_temp: float                   # Average temperature (°C)
    condition: str                    # Weather condition
    weather_code: int                 # Tomorrow.io weather code
```

## Running Real Backtests

### Option 1: CLI (Easiest)

```bash
# Setup
cp .env.sample.extended .env
# Edit .env and add TOMORROWIO_API_KEY

# Run
python3 real_backtest_cli.py
```

Output:
- Console report with strategy performance
- JSON results: `test-results/real_backtest_results_*.json`
- Text report: `test-results/real_backtest_report_*.txt`

### Option 2: Python Script

```python
import asyncio
import os
from utils.real_backtest_util import run_real_backtest

async def main():
    tomorrow_io_key = os.getenv("TOMORROWIO_API_KEY")
    
    results = await run_real_backtest(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=None,  # Optional
        output_dir="test-results"
    )
    
    print(f"Trades executed: {results['trading_results']['trades_executed']}")
    print(f"ROI: {results['trading_results']['roi_percentage']:.2f}%")

asyncio.run(main())
```

### Option 3: Tests

```bash
# Run real backtest tests
pytest tests/backtests/test_real_backtest.py -v

# Run all tests
pytest tests/ -v
```

## API Configuration

### Tomorrow.io API Key

1. Visit: https://www.tomorrow.io/weather-api/
2. Sign up for free account
3. Get API key from dashboard
4. Add to `.env`:
   ```
   TOMORROWIO_API_KEY=your_key_here
   ```

### Polymarket API (Optional)

- Free public API, no authentication required
- Optional API key for higher rate limits
- Add to `.env`:
   ```
   POLYMARKET_API_KEY=your_key_here
   ```

## Backtest Results

### Report Format

```
======================================================================
POLYMARKET REAL DATA BACKTEST REPORT
======================================================================

BACKTEST INFORMATION
----------------------------------------------------------------------
Timestamp:              2026-01-25T06:10:39.417402
Data Source:            Real API Data (Polymarket + Tomorrow.io)
Markets Analyzed:       100
Cities Covered:         London, New York, Seoul

DATA ANALYSIS
----------------------------------------------------------------------
Markets Analyzed:       100
Opportunities Found:    45
BUY Signals Generated:  12

TRADING RESULTS
----------------------------------------------------------------------
Trades Executed:        12
Initial Capital:        $197.00
Final Capital:          $2,847.50
Total Profit:           $2,650.50
Total ROI:              1346.70%
Winning Trades:         11
Losing Trades:          1
Win Rate:               91.7%

STRATEGY PARAMETERS
----------------------------------------------------------------------
Min Liquidity:          $50.00
Min Edge:               15.0%
Max Price:              $0.1000
Min Confidence:         60.0%

SAMPLE MARKETS ANALYZED
----------------------------------------------------------------------
1. London: Will London temperature exceed 75°F?
   Price: $0.08, Liquidity: $150.00
2. New York: Will New York temperature exceed 70°F?
   Price: $0.06, Liquidity: $100.00
```

### JSON Output

```json
{
  "backtest_info": {
    "timestamp": "2026-01-25T06:10:39.417402",
    "data_source": "Real API Data (Polymarket + Tomorrow.io)",
    "markets_analyzed": 100,
    "cities_covered": ["London", "New York", "Seoul"]
  },
  "data_points": {
    "markets_analyzed": 100,
    "opportunities_identified": 45,
    "buy_signals": 12
  },
  "trading_results": {
    "trades_executed": 12,
    "initial_capital": 197.0,
    "final_capital": 2847.5,
    "total_profit": 2650.5,
    "roi_percentage": 1346.7,
    "winning_trades": 11,
    "losing_trades": 1,
    "win_rate": 91.7
  },
  "strategy_parameters": {
    "min_liquidity": 50.0,
    "min_edge": 0.15,
    "max_price": 0.1,
    "min_confidence": 0.6
  }
}
```

## Test Coverage

### Real Backtest Tests (13 tests)

| Category | Tests | Purpose |
|----------|-------|---------|
| Data Fetcher | 7 | Test API integration and data parsing |
| Backtest Engine | 3 | Test backtest logic with real data |
| Reporter | 2 | Test report generation |
| Integration | 1 | Test complete workflow |

### All Tests

| Category | Tests | Type | Status |
|----------|-------|------|--------|
| Unit Tests | 21 | Mocked | ✅ Passing |
| Synthetic Backtest | 16 | Generated | ✅ Passing |
| Real Backtest | 13 | API Data | ✅ Passing |
| **Total** | **50** | **Mixed** | **✅ All Passing** |

## Troubleshooting

### API Key Errors

**Error:** `TOMORROWIO_API_KEY environment variable not set`

**Solution:**
```bash
# Create .env file
echo "TOMORROWIO_API_KEY=your_key_here" > .env

# Or set environment variable
export TOMORROWIO_API_KEY=your_key_here
```

### No Markets Found

**Causes:**
- Polymarket API temporarily unavailable
- No weather-related markets currently active
- Network connectivity issues

**Solution:**
```bash
# Check API directly
curl "https://gamma-api.polymarket.com/markets?search=weather&limit=10"

# Check Tomorrow.io
curl "https://api.tomorrow.io/v4/weather/forecast?location=51.5074,-0.1278&apikey=YOUR_KEY&timesteps=1d"
```

### Temperature Unit Mismatch

Tomorrow.io returns temperatures in **Celsius** by default.
The code automatically handles conversion for comparison.

## Performance Considerations

### API Rate Limits

- **Polymarket:** No public rate limit (free API)
- **Tomorrow.io:** 500 calls/day (free tier)

### Backtest Duration

- Fetching markets: ~2-5 seconds
- Fetching weather: ~2-5 seconds (per city)
- Running backtest: <1 second
- Total: ~5-15 seconds

### Optimization Tips

1. **Reduce market limit:**
   ```python
   markets = await fetcher.fetch_polymarket_weather_markets(limit=50)
   ```

2. **Cache API responses:**
   ```python
   # Save to file and reload
   with open("markets.json", "w") as f:
       json.dump([asdict(m) for m in markets], f)
   ```

3. **Use specific cities:**
   ```python
   weather = await fetcher.fetch_all_cities_weather(
       cities=["London"]  # Single city
   )
   ```

## Advanced Usage

### Custom Strategy

```python
from agent.tools.trading_strategy import TradingStrategy
from utils.real_backtest_util import RealBacktestEngine

strategy = TradingStrategy(
    min_liquidity=100.0,    # Higher minimum
    min_edge=0.20,          # Higher edge requirement
    max_price=0.05,         # Lower max price
    min_confidence=0.70,    # Higher confidence
)

engine = RealBacktestEngine(strategy=strategy)
results = engine.run_backtest(markets, weather_data)
```

### Batch Backtests

```python
import asyncio
from utils.real_backtest_util import run_real_backtest

async def run_multiple_backtests():
    for i in range(5):
        results = await run_real_backtest(
            tomorrow_io_key=os.getenv("TOMORROWIO_API_KEY"),
            output_dir=f"test-results/run_{i}"
        )
        print(f"Run {i}: ROI = {results['trading_results']['roi_percentage']:.2f}%")

asyncio.run(run_multiple_backtests())
```

## Next Steps

1. **Get API Key:** Sign up at Tomorrow.io
2. **Run CLI:** `python3 real_backtest_cli.py`
3. **Review Results:** Check `test-results/` directory
4. **Adjust Strategy:** Modify parameters in `.env`
5. **Run Tests:** `pytest tests/backtests/test_real_backtest.py -v`

## References

- [Tomorrow.io API Docs](https://docs.tomorrow.io/reference/welcome)
- [Polymarket Gamma API](https://docs.polymarket.com/polymarket-learn/get-started/what-is-polymarket)
- [Strategy Implementation](../agent/tools/trading_strategy.py)
- [Test Examples](../tests/backtests/test_real_backtest.py)

---

**Last Updated:** January 25, 2026  
**Version:** 1.0  
**Status:** Production Ready
