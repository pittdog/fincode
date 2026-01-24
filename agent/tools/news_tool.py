import os
import json
import httpx
from typing import Optional, Any
from datetime import datetime
from model.llm import LLMProvider

class NewsTool:
    """Tool for fetching news using xAI (Grok) or Tavily."""

    def __init__(self, llm: Optional[Any] = None):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.tavily_url = "https://api.tavily.com/search"
        self.client = httpx.Client(timeout=30.0)
        
        # Use provided LLM or initialize a fast Grok-3 instance if possible
        self.llm = llm
        if not self.llm and os.getenv("XAI_API_KEY"):
            try:
                self.llm = LLMProvider.get_model("grok-3", "xai", temperature=0.1)
            except:
                pass

    def get_news(self, query: str, max_results: int = 5) -> str:
        """
        Fetch news for a given query or ticker.
        Tries xAI (Grok) first, then falls back to Tavily.
        """
        results = {"provider": "unknown", "news": []}

        # 1. Try xAI (Grok) - Fastest for real-time summaries with citations
        if self.llm:
            try:
                prompt = (
                    f"You are a financial news assistant. Provide the latest news for {query}. "
                    "For each news item, provide a brief summary and the source/link. "
                    "Format as a JSON list of objects with 'title', 'summary', and 'source'. "
                    "Only return the JSON list."
                )
                response = self.llm.invoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                
                # Try to extract JSON array
                import re
                content = content.strip()
                # Remove markdown code blocks if present
                content = re.sub(r"```json\s*", "", content)
                content = re.sub(r"```\s*", "", content)
                
                json_match = re.search(r"\[\s*\{.*\}\s*\]", content, re.DOTALL)
                if json_match:
                    news_items = json.loads(json_match.group(0))
                    return json.dumps({
                        "provider": "xAI (Grok-3)",
                        "ticker": query,
                        "timestamp": datetime.now().isoformat(),
                        "results": news_items
                    })
            except Exception as e:
                pass # Fallback to Tavily

        # 2. Fallback to Tavily
        if not self.tavily_api_key:
            return json.dumps({"error": "No news provider (xAI or Tavily) available."})

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
            data = response.json()
            return json.dumps({
                "provider": "Tavily",
                "ticker": query,
                "timestamp": datetime.now().isoformat(),
                "results": data.get("results", [])
            })
        except Exception as e:
            return json.dumps({"error": f"Tavily News Failed: {str(e)}"})

    def close(self):
        self.client.close()
