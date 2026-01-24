import os
import json
from dotenv import load_dotenv
from agent.tools.ticker_tool import TickerTool

load_dotenv()

def test_quote_direct():
    tool = TickerTool()
    ticker = "MSFT"
    api_key = os.getenv("MASSIVE_API_KEY")
    base_url = "https://api.massive.com"
    
    print(f"Testing direct ticker details for {ticker}...")
    details = tool.get_ticker_details(ticker)
    print("\n--- BASE DETAILS ---")
    print(details[:500] + "...")

    endpoints = [
        f"/v2/aggs/ticker/{ticker}/prev",
        f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting endpoint: {endpoint}")
        try:
            response = tool.client.get(f"{base_url}{endpoint}", params={"apiKey": api_key})
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print(json.dumps(response.json(), indent=2))
            else:
                print(response.text)
        except Exception as e:
            print(f"Error: {e}")

    tool.close()

if __name__ == "__main__":
    test_quote_direct()
