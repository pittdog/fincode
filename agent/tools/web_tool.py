import os
import json
import httpx
from typing import Optional

class WebSearchTool:
    """Tool for general web search using Tavily API."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"
        self.client = httpx.Client(timeout=30.0)

    def search(self, query: str, max_results: int = 5) -> str:
        """
        Search the web for information.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
        """
        if not self.api_key:
            return json.dumps({"error": "TAVILY_API_KEY not configured"})

        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
            }

            response = self.client.post(self.base_url, json=payload)
            response.raise_for_status()
            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    def close(self):
        self.client.close()
