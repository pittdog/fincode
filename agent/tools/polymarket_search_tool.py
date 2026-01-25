"""Tool for searching weather markets on Polymarket with deep CLOB integration."""
import logging
from typing import List, Optional, Dict, Any
from .polymarket_tool import PolymarketClient, PolymarketMarket
from .polymarket_clob_api import PolymarketCLOBClient

logger = logging.getLogger(__name__)

class WeatherSearchTool:
    """Tool for targeted searching of weather-related markets with order book details."""

    WEATHER_KEYWORDS = [
        "temperature", "weather", "rain", "snow", "degree", 
        "celsius", "fahrenheit", "heat", "cold", "climate"
    ]

    def __init__(self, client: Optional[PolymarketClient] = None, clob_client: Optional[PolymarketCLOBClient] = None):
        self.client = client
        self.clob_client = clob_client

    async def _setup_clients(self):
        if self.client is None:
            from .polymarket_tool import get_polymarket_client
            self.client = await get_polymarket_client()
        if self.clob_client is None:
            import os
            self.clob_client = PolymarketCLOBClient(key=os.getenv("POLYMARKET_PRIVATE_KEY"))

    async def search(
        self, 
        query: str = "temperature", 
        city: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for weather markets and enrich with detailed CLOB order book data.
        
        Args:
            query: Search query
            city: Optional city filter
            limit: Max results
            
        Returns:
            List of markets with question, ID, and detailed bid/ask info
        """
        await self._setup_clients()
        
        search_query = query
        if city:
            search_query = f"{query} {city}"
            
        # 1. Search Gamma (Public Search)
        markets = await self.client.gamma_search(q=search_query, limit=limit)
        logger.info(f"Gamma search for '{search_query}' returned {len(markets)} markets")
        
        results = []
        for m in markets:
            # 2. Verify it's actually weather related
            q_lower = m.question.lower()
            if not any(kw in q_lower for kw in self.WEATHER_KEYWORDS):
                continue
            
            # 3. Get CLOB Order Book for YES/NO tokens
            book_info = {}
            if m.clob_token_ids:
                # Typically index 0 is YES, 1 is NO
                # For weather, we usually care about YES
                token_id = m.clob_token_ids[0]
                book = await self.clob_client.get_order_book(token_id, question=m.question)
                if book:
                    book_info = {
                        "best_bid": book.best_bid,
                        "best_ask": book.best_ask,
                        "spread": book.spread,
                        "token_id": token_id
                    }

            results.append({
                "id": m.id,
                "question": m.question,
                "liquidity": m.liquidity,
                "volume": m.volume,
                "yes_price": m.yes_price,
                "clob_details": book_info
            })

        # Sort by liquidity for better quality
        return sorted(results, key=lambda x: x["liquidity"], reverse=True)
