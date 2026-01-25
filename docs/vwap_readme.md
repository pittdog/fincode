# Volume-Weighted Average Price (VWAP) Implementation

## Overview
To provide a more realistic "Fair Value" for weather markets with thin order books, we use Volume-Weighted Average Price (VWAP) instead of a simple mid-price calculation.

## Why VWAP?
Weather markets often have extreme "best bid" and "best ask" prices (e.g., $0.001 bid and $0.999 ask) which results in a misleading 50% mid-price. VWAP looks at the entire order book depth to find where the actual capital is sitting.

## Calculation Formula

The VWAP is calculated separately for both Bids and Asks across the entire available L2 depth:

$$VWAP = \frac{\sum (Price_i \times Size_i)}{\sum Size_i}$$

Where:
- $Price_i$ is the price of the $i$-th order in the book.
- $Size_i$ is the quantity of shares at that price.

## Fair Value Calculation
The "Fair Value" displayed in the table is the average of the Bid VWAP and the Ask VWAP:

$$Fair\ Value = \frac{Bid_{VWAP} + Ask_{VWAP}}{2}$$

## Implementation Details
The calculation is performed in `agent/tools/polymarket_clob_api.py` within the `get_order_book` method.

```python
# Bid VWAP calculation
if bids_list:
    bid_vwap = sum(b["price"] * b["size"] for b in bids_list) / sum(b["size"] for b in bids_list)
else:
    bid_vwap = 0.0

# Ask VWAP calculation
if asks_list:
    ask_vwap = sum(a["price"] * a["size"] for a in asks_list) / sum(a["size"] for a in asks_list)
else:
    ask_vwap = 1.0

# Fair Value
mid_price = (bid_vwap + ask_vwap) / 2
```

## Benefis
- **Anti-Gouging**: Ignores empty orders at $0.001 or $0.999 if there is significant volume at better prices.
- **Realistic Probability**: Reflects the actual consensus price of active market participants.
- **Tradeability Indicator**: If VWAP differs significantly from best bid/ask, it indicates a "hollow" book.
