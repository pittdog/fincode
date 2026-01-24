import os
import json
import httpx
from typing import Optional

class TickerTool:
    """Tool for loading detailed ticker information using Massive (Polygon) API."""

    def __init__(self):
        self.api_key = os.getenv("MASSIVE_API_KEY")
        self.base_url = "https://api.massive.com"
        self.client = httpx.Client(timeout=30.0)

    def get_ticker_details(self, ticker: str) -> str:
        """
        Get detailed information about a stock ticker.
        
        Args:
            ticker: The stock ticker symbol (e.g., AAPL)
        """
        if not self.api_key:
            return json.dumps({"error": "MASSIVE_API_KEY not configured"})

        try:
            # 1. Get Ticker Details (Reference Data)
            response = self.client.get(
                f"{self.base_url}/v3/reference/tickers/{ticker.upper()}",
                params={"apiKey": self.api_key}
            )
            response.raise_for_status()
            details_data = response.json()
            results = details_data.get("results", {})

            # 2. Get Snapshot (Real-time Price/Quote Data)
            try:
                snap_response = self.client.get(
                    f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}",
                    params={"apiKey": self.api_key}
                )
                if snap_response.status_code == 200:
                    snap_data = snap_response.json().get("ticker", {})
                    # Merge relevant price data into results
                    results["price_data"] = {
                        "day": snap_data.get("day", {}),
                        "prevDay": snap_data.get("prevDay", {}),
                        "todaysChange": snap_data.get("todaysChange"),
                        "todaysChangePerc": snap_data.get("todaysChangePerc"),
                        "updated": snap_data.get("updated")
                    }
            except:
                pass # Continue with just details if snapshot fails

            return json.dumps(results)
        except Exception as e:
            # Fallback to search if specific ticker fails or if v2 is needed
            try:
                response = self.client.get(
                    f"{self.base_url}/v2/reference/tickers",
                    params={"ticker": ticker.upper(), "apiKey": self.api_key}
                )
                response.raise_for_status()
                return json.dumps(response.json())
            except:
                return json.dumps({"error": str(e)})

    def close(self):
        self.client.close()
