import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.backtest_engine import BacktestEngine
from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.visual_crossing_client import VisualCrossingClient

async def test_backtest_logic_flow():
    # Mock clients
    pm_mock = MagicMock(spec=PolymarketClient)
    vc_mock = MagicMock(spec=VisualCrossingClient)
    
    # Mock Market
    market_mock = MagicMock()
    market_mock.question = "Will London temperature exceed 70F?"
    market_mock.id = "london-123"
    market_mock.liquidity = 100.0
    pm_mock.get_market_by_id = AsyncMock(return_value=market_mock)
    
    # Mock Price History
    # Use timestamps that match the current range or adjusted range
    # Jan 20-22, 2026 timestamps
    pm_mock.get_price_history = AsyncMock(return_value=[
        {"t": int(datetime(2026, 1, 20).timestamp()), "y": 0.1},
        {"t": int(datetime(2026, 1, 21).timestamp()), "y": 0.15},
        {"t": int(datetime(2026, 1, 22).timestamp()), "y": 0.12}
    ])
    
    # Mock Weather
    vc_mock.get_day_weather = AsyncMock(return_value={
        "tempmax": 75, "tempmin": 65, "temp": 70
    })
    
    engine = BacktestEngine(pm_mock, vc_mock)
    
    # Run backtest for a date in the range
    result = await engine.run_backtest("London", "2026-01-26", "london-123")
    
    print(f"\nTest Result: {result.get('success')}")
    if not result.get("success"):
        print(f"Error: {result.get('error')}")
    
    assert result["success"] is True
    assert result["city"] == "London"
    assert result["num_price_points"] > 0
    assert "pnl" in result
    print("Backtest logic flow test passed!")

if __name__ == "__main__":
    asyncio.run(test_backtest_logic_flow())
