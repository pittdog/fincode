"""Polymarket CLOB API client for real trade history."""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class PolymarketCLOBClient:
    """Client for Polymarket CLOB API to fetch real trade history."""
    
    # CLOB API endpoints
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize CLOB client.
        
        Args:
            api_key: Optional API key for authenticated endpoints
        """
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30)
        self.headers = {}
        
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def get_markets(
        self,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get markets from CLOB API.
        
        Args:
            search: Search query
            limit: Number of markets to return
            offset: Offset for pagination
            
        Returns:
            List of markets
        """
        try:
            url = f"{self.BASE_URL}/markets"
            params = {
                "limit": limit,
                "offset": offset,
            }
            
            if search:
                params["search"] = search
            
            logger.info(f"Fetching markets from CLOB API: {url}")
            response = await self.client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            markets = data.get("markets", []) if isinstance(data, dict) else data
            
            logger.info(f"Fetched {len(markets)} markets")
            return markets
        
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    async def get_market_by_id(self, market_id: str) -> Dict[str, Any]:
        """Get specific market by ID.
        
        Args:
            market_id: Market ID
            
        Returns:
            Market data
        """
        try:
            url = f"{self.BASE_URL}/markets/{market_id}"
            
            logger.info(f"Fetching market {market_id}")
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return {}
    
    async def get_trades(
        self,
        market_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get trades from CLOB API.
        
        Args:
            market_id: Optional market ID to filter trades
            limit: Number of trades to return
            offset: Offset for pagination
            
        Returns:
            List of trades
        """
        try:
            url = f"{self.BASE_URL}/trades"
            params = {
                "limit": limit,
                "offset": offset,
            }
            
            if market_id:
                params["market_id"] = market_id
            
            logger.info(f"Fetching trades from CLOB API")
            response = await self.client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            trades = data.get("trades", []) if isinstance(data, dict) else data
            
            logger.info(f"Fetched {len(trades)} trades")
            return trades
        
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    async def get_orders(
        self,
        market_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get orders from CLOB API.
        
        Args:
            market_id: Optional market ID to filter orders
            limit: Number of orders to return
            offset: Offset for pagination
            
        Returns:
            List of orders
        """
        try:
            url = f"{self.BASE_URL}/orders"
            params = {
                "limit": limit,
                "offset": offset,
            }
            
            if market_id:
                params["market_id"] = market_id
            
            logger.info(f"Fetching orders from CLOB API")
            response = await self.client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            orders = data.get("orders", []) if isinstance(data, dict) else data
            
            logger.info(f"Fetched {len(orders)} orders")
            return orders
        
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []
    
    async def get_market_trades(
        self,
        market_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all trades for a specific market.
        
        Args:
            market_id: Market ID
            limit: Number of trades to return
            
        Returns:
            List of trades for the market
        """
        try:
            url = f"{self.BASE_URL}/markets/{market_id}/trades"
            params = {"limit": limit}
            
            logger.info(f"Fetching trades for market {market_id}")
            response = await self.client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            trades = data.get("trades", []) if isinstance(data, dict) else data
            
            logger.info(f"Fetched {len(trades)} trades for market {market_id}")
            return trades
        
        except Exception as e:
            logger.error(f"Error fetching trades for market {market_id}: {e}")
            return []
    
    async def get_market_orderbook(self, market_id: str) -> Dict[str, Any]:
        """Get order book for a specific market.
        
        Args:
            market_id: Market ID
            
        Returns:
            Order book data
        """
        try:
            url = f"{self.BASE_URL}/markets/{market_id}/orderbook"
            
            logger.info(f"Fetching orderbook for market {market_id}")
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(f"Error fetching orderbook for market {market_id}: {e}")
            return {}
    
    async def get_historical_prices(
        self,
        market_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical prices for a market.
        
        Args:
            market_id: Market ID
            start_time: Start time for historical data
            end_time: End time for historical data
            
        Returns:
            List of historical price points
        """
        try:
            url = f"{self.BASE_URL}/markets/{market_id}/prices"
            params = {}
            
            if start_time:
                params["start_time"] = start_time.isoformat()
            if end_time:
                params["end_time"] = end_time.isoformat()
            
            logger.info(f"Fetching historical prices for market {market_id}")
            response = await self.client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            prices = data.get("prices", []) if isinstance(data, dict) else data
            
            logger.info(f"Fetched {len(prices)} price points")
            return prices
        
        except Exception as e:
            logger.error(f"Error fetching historical prices: {e}")
            return []
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


async def fetch_real_trades_from_clob(
    api_key: Optional[str] = None,
    search_query: str = "weather",
    num_trades: int = 50,
) -> List[Dict[str, Any]]:
    """Fetch real trades from Polymarket CLOB API.
    
    Args:
        api_key: Optional API key for authenticated access
        search_query: Search query for markets
        num_trades: Number of trades to fetch
        
    Returns:
        List of real trades
    """
    client = PolymarketCLOBClient(api_key=api_key)
    
    try:
        print("\n" + "=" * 70)
        print("FETCHING REAL TRADES FROM POLYMARKET CLOB API")
        print("=" * 70)
        
        # Fetch weather markets
        print(f"\n1. Searching for '{search_query}' markets...")
        markets = await client.get_markets(search=search_query, limit=20)
        
        if not markets:
            print("❌ No markets found")
            return []
        
        print(f"✓ Found {len(markets)} markets")
        
        # Fetch trades for each market
        all_trades = []
        for market in markets[:5]:  # Limit to first 5 markets
            market_id = market.get("id")
            question = market.get("question", "")
            
            print(f"\n2. Fetching trades for: {question[:60]}...")
            
            trades = await client.get_market_trades(market_id, limit=10)
            
            if trades:
                print(f"   ✓ Found {len(trades)} trades")
                all_trades.extend(trades)
            else:
                print(f"   ⚠️  No trades found")
        
        print(f"\n✓ Total real trades fetched: {len(all_trades)}")
        return all_trades
    
    finally:
        await client.close()


if __name__ == "__main__":
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Get API key from environment
    api_key = os.getenv("POLYMARKET_CLOB_API_KEY")
    
    # Fetch real trades
    trades = asyncio.run(fetch_real_trades_from_clob(
        api_key=api_key,
        search_query="weather",
        num_trades=50,
    ))
    
    if trades:
        print("\n" + "=" * 70)
        print("SAMPLE TRADES")
        print("=" * 70)
        for i, trade in enumerate(trades[:3]):
            print(f"\nTrade {i+1}:")
            print(json.dumps(trade, indent=2, default=str)[:500])
