# Implementation Plan - Integrate Polymarket Agent

The goal is to integrate the standalone Polymarket trading agent into the main `fincode` CLI, adding CLOB support and specific commands `poly:weather` and `poly:buy`.

## User Review Required
> [!NOTE]
> `poly:buy` will simulated using **Real CLOB Data** (bids/asks). It will not execute on-chain transactions as the [CLOB_API_INTEGRATION.md](file:///Users/askariot/Project/fincode/docs/CLOB_API_INTEGRATION.md) provided does not detail the order signing/submission endpoints, only data retrieval.
> We will verify "Tomorrow" logic by matching the forecast date with market end dates.

## Proposed Changes

### Agent Tools
#### [NEW] [agent/tools/polymarket_clob_api.py](file:///Users/askariot/Project/fincode/agent/tools/polymarket_clob_api.py)
- Implement `PolymarketCLOBClient` as described in [docs/CLOB_API_INTEGRATION.md](file:///Users/askariot/Project/fincode/docs/CLOB_API_INTEGRATION.md).
- Methods: [get_markets](file:///Users/askariot/Project/fincode/agent/tools/polymarket_tool.py#62-110), [get_order_book](file:///Users/askariot/Project/fincode/agent/tools/polymarket_tool.py#132-168), `get_trades`.

#### [NEW] [agent/tools/polymarket_wrapper.py](file:///Users/askariot/Project/fincode/agent/tools/polymarket_wrapper.py)
- A high-level wrapper combining [PolymarketClient](file:///Users/askariot/Project/fincode/agent/tools/polymarket_tool.py#36-235) (Gamma), `PolymarketCLOBClient` (CLOB), and [WeatherClient](file:///Users/askariot/Project/fincode/agent/tools/weather_tool.py#28-253).
- **Logic**:
    - `scan_weather_opportunities()`:
        1. Scan Gamma API for weather markets.
        2. Filter for `end_date` == Tomorrow.
        3. Fetch Weather Forecast for cities.
        4. Fetch CLOB Orderbook for precise pricing.
        5. Analyze edge.
        6. Return sorted opportunities.
    - [simulate_trade(market_id, amount, side)](file:///Users/askariot/Project/fincode/polyagent_cli.py#229-263):
        1. Fetch CLOB Orderbook.
        2. Simulate execution against the order book (walking the book).
        3. Return simulated price usage and slippage.

#### [MODIFY] [agent/tools/__init__.py](file:///Users/askariot/Project/fincode/agent/tools/__init__.py)
- Export `PolymarketWrapper` and `PolymarketCLOBClient`.

### Agent Configuration
#### [MODIFY] [agent/agent.py](file:///Users/askariot/Project/fincode/agent/agent.py)
- Register `polymarket_analysis` tool (wraps `scan_weather_opportunities`) for the AI.

### Command Processor
#### [MODIFY] [components/command_processor.py](file:///Users/askariot/Project/fincode/components/command_processor.py)
- **poly:weather**:
    - Calls `wrapper.scan_weather_opportunities()`.
    - Displays "Best Opportunities" table.
- **poly:buy <amount> <market_id>**:
    - Calls `wrapper.simulate_trade(...)`.
    - Displays trade simulation results (Simulated Vwap, etc.).

## Verification Plan

### Automated Tests
- Create `tests/test_clob_integration.py` to verify `PolymarketCLOBClient` (mocked).
- Update [tests/test_polyagent.py](file:///Users/askariot/Project/fincode/tests/test_polyagent.py) if needed.

### Manual Verification
1. `poly:weather`: Run and verify it only shows markets ending tomorrow.
2. `poly:buy 10 <id>`: Verify it calculates price based on loaded order book.
