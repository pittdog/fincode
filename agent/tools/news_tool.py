import os
import json
import httpx
from typing import Optional, List

class NewsTool:
    """Tool for fetching news using Tavily and potentially summarizing with XAI."""

    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.tavily_url = "https://api.tavily.com/search"
        self.client = httpx.Client(timeout=30.0)

    def get_news(self, query: str, max_results: int = 5) -> str:
        """
        Fetch news for a given query or ticker.
        
        Args:
            query: The topic or ticker to search news for.
            max_results: Number of news results to return.
        """
        if not self.tavily_api_key:
            return json.dumps({"error": "TAVILY_API_KEY not configured"})

        try:
            payload = {
                "api_key": self.tavily_api_key,
                "query": f"latest financial news for {query}",
                "search_depth": "advanced",
                "topic": "news",
                "max_results": max_results,
            }
            
            response = self.client.post(self.tavily_url, json=payload)
            response.raise_for_status()
            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    def close(self):
        self.client.close()
