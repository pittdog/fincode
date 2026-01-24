import os
import json
import asyncio
from dotenv import load_dotenv
from agent.tools.news_tool import NewsTool

load_dotenv()

def test_news_direct():
    tool = NewsTool()
    ticker = "AMZN"
    print(f"Testing direct news for {ticker}...")
    
    result_json = tool.get_news(ticker)
    result = json.loads(result_json)
    
    print(f"Provider: {result.get('provider')}")
    print(f"Ticker: {result.get('ticker')}")
    
    results = result.get("results", [])
    print(f"Found {len(results)} news items.")
    
    if results:
        item = results[0]
        print(f"\nSample Item:")
        print(f"Title: {item.get('title')}")
        print(f"Source: {item.get('source') or item.get('url')}")
    
    tool.close()

if __name__ == "__main__":
    test_news_direct()
