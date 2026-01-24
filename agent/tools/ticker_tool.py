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
            # Using v3 reference ticker details API
            response = self.client.get(
                f"{self.base_url}/v3/reference/tickers/{ticker.upper()}",
                params={"apiKey": self.api_key}
            )
            response.raise_for_status()
            data = response.json()
            
            if "results" in data:
                return json.dumps(data["results"])
            return json.dumps(data)
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
