import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

def test_massive_api():
    """Simple test for Massive (Polygon) API connectivity and structure."""
    api_key = os.getenv("MASSIVE_API_KEY")
    base_url = "https://api.massive.com"
    ticker = "AMZN"

    params = {
        "ticker": ticker,
        "apiKey": api_key,
        "limit": 1
    }

    print(f"Calling Massive API for {ticker}...")
    response = httpx.get(f"{base_url}/vX/reference/financials", params=params)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"API call failed: {response.text}"
    
    data = response.json()
    assert "results" in data, "No results in response"
    assert len(data["results"]) > 0, f"No financial filings found for {ticker}"
    
    result = data["results"][0]
    assert "financials" in result, "No financials object in filing"
    
    financials = result["financials"]
    print("Available statements:", list(financials.keys()))
    
    # Check for core statements
    expected = ["income_statement", "balance_sheet", "cash_flow_statement"]
    found = [k for k in expected if k in financials]
    print(f"Found statements: {found}")
    
    assert len(found) > 0, "No standard financial statements found in filing"

if __name__ == "__main__":
    test_massive_api()
    print("✓ Massive API verification successful")
