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
        
        # Use provided LLM or initialize a fast instance if possible
        self.llm = llm
        if not self.llm:
            model = os.getenv("MODEL", "grok-3")
            provider = os.getenv("MODEL_PROVIDER", "xai")
            if provider == "xai" and os.getenv("XAI_API_KEY"):
                try:
                    self.llm = LLMProvider.get_model(model, provider, temperature=0.1)
                except:
                    pass

    def get_news(self, query: str, max_results: int = 5) -> str:
        """
        Fetch news for a given query or ticker.
        Tries xAI (Grok) first with real-time X search prompt, then falls back to Tavily.
        """
        from pathlib import Path

        # 1. Try xAI (Grok) - Using the markdown prompt
        if self.llm:
            try:
                prompt_path = Path("agent/prompts/news_prompt.md")
                if not prompt_path.exists():
                    # Check absolute path relative to project root if necessary
                    prompt_path = Path(__file__).parent.parent / "prompts" / "news_prompt.md"
                
                prompt_template = prompt_path.read_text()
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                prompt = prompt_template.replace("{{current_time}}", current_time).replace("{{topic}}", query)
                
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
                    provider_label = f"{os.getenv('MODEL_PROVIDER', 'xai').upper()} ({os.getenv('MODEL', 'grok-3')})"
                    return json.dumps({
                        "provider": provider_label,
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
