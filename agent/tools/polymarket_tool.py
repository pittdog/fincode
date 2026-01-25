"""Polymarket API client for fetching market data and weather conditions."""
import httpx
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class PolymarketMarket:
    """Represents a Polymarket market."""
    id: str
    question: str
    description: str
    outcomes: List[str]
    yes_price: float
    no_price: float
    liquidity: float
    volume: float
    created_at: str
    end_date: str
    condition_id: Optional[str] = None
    clob_token_ids: Optional[List[str]] = None


@dataclass
class OrderBook:
    """Represents an order book for a market."""
    market_id: str
    bids: List[Dict[str, Any]]
    asks: List[Dict[str, Any]]
    mid_price: float


class PolymarketClient:
    """Client for interacting with Polymarket API."""

    BASE_URL = "https://gamma-api.polymarket.com"
    MARKETS_ENDPOINT = "/markets"
    ORDER_BOOK_ENDPOINT = "/order-book"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Polymarket client.
        
        Args:
            api_key: Optional API key for authenticated endpoints
        """
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_markets(
        self,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "volume",
        active: bool = True,
        closed: bool = False,
    ) -> List[PolymarketMarket]:
        """Fetch markets from Polymarket."""
        try:
            params = {
                "limit": limit,
                "offset": offset,
                "sortBy": sort_by,
                "active": "true" if active else "false",
                "closed": "true" if closed else "false",
            }
            if search:
                params["search"] = search

            response = await self.client.get(
                f"{self.BASE_URL}{self.MARKETS_ENDPOINT}",
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

            markets_data = data if isinstance(data, list) else data.get("data", [])
            markets = []
            for market_data in markets_data:
                try:
                    market = self._parse_market(market_data)
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    async def gamma_search(self, q: str, status: str = "active", limit: int = 50) -> List[PolymarketMarket]:
        """Search Polymarket using the public-search endpoint (favored for keyword search)."""
        try:
            params = {
                "q": q,
                "events_status": status,
                "limit_per_type": limit
            }
            response = await self.client.get(
                f"{self.BASE_URL}/public-search",
                params=params,
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            
            # Gamma search returns results grouped by type: 'events' containing 'markets'
            events = data.get("events", [])
            all_markets = []
            for event in events:
                event_markets = event.get("markets", [])
                for m in event_markets:
                    all_markets.append(self._parse_market(m))
            
            # Also check for top-level 'markets' if any (sometimes included)
            direct_markets = data.get("markets", [])
            for m in direct_markets:
                all_markets.append(self._parse_market(m))

            return all_markets
        except Exception as e:
            logger.error(f"Error in gamma_search for '{q}': {e}")
            return []

    async def get_market_by_id(self, market_id: str) -> Optional[PolymarketMarket]:
        """Fetch a specific market by ID.
        
        Args:
            market_id: The market ID
            
        Returns:
            PolymarketMarket object or None if not found
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}{self.MARKETS_ENDPOINT}/{market_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_market(data)
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return None

    async def get_order_book(self, market_id: str) -> Optional[OrderBook]:
        """Fetch order book for a market.
        
        Args:
            market_id: The market ID
            
        Returns:
            OrderBook object or None if not found
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}{self.ORDER_BOOK_ENDPOINT}/{market_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            # Calculate mid price
            mid_price = 0.5
            if bids and asks:
                best_bid = max(float(bid[0]) for bid in bids) if bids else 0
                best_ask = min(float(ask[0]) for ask in asks) if asks else 1
                mid_price = (best_bid + best_ask) / 2

            return OrderBook(
                market_id=market_id,
                bids=bids,
                asks=asks,
                mid_price=mid_price,
            )
        except Exception as e:
            logger.error(f"Error fetching order book for {market_id}: {e}")
            return None

    async def search_weather_markets(
        self,
        cities: Optional[List[str]] = None,
        min_liquidity: float = 50.0,
        max_price: float = 0.10,
    ) -> List[PolymarketMarket]:
        """Search for weather markets with specific criteria.
        
        Args:
            cities: List of cities to search for (e.g., ["London", "New York"])
            min_liquidity: Minimum liquidity threshold
            max_price: Maximum price threshold for YES token
            
        Returns:
            List of matching markets
        """
        markets = []
        cities = cities or ["London", "New York", "Seoul"]

        for city in cities:
            try:
                search_query = f"weather {city} temperature"
                city_markets = await self.get_markets(
                    search=search_query,
                    limit=50,
                )

                for market in city_markets:
                    # Filter by criteria
                    if (
                        market.liquidity >= min_liquidity
                        and market.yes_price <= max_price
                    ):
                        markets.append(market)
            except Exception as e:
                logger.warning(f"Error searching markets for {city}: {e}")
                continue

        return markets

    def _parse_market(self, data: Dict[str, Any]) -> PolymarketMarket:
        """Parse raw market data into PolymarketMarket object.
        
        Args:
            data: Raw market data from API
            
        Returns:
            PolymarketMarket object
        """
        # Extract YES price (typically index 0)
        prices = data.get("prices", [0.5, 0.5])
        yes_price = float(prices[0]) if prices else 0.5
        no_price = float(prices[1]) if len(prices) > 1 else (1 - yes_price)

        clob_token_ids = data.get("clobTokenIds", [])
        if isinstance(clob_token_ids, str) and clob_token_ids.strip():
            try:
                clob_token_ids = json.loads(clob_token_ids)
            except:
                clob_token_ids = []

        return PolymarketMarket(
            id=data.get("id", ""),
            question=data.get("question", ""),
            description=data.get("description", ""),
            outcomes=data.get("outcomes", ["Yes", "No"]),
            yes_price=yes_price,
            no_price=no_price,
            liquidity=float(data.get("liquidity", 0)),
            volume=float(data.get("volume24h", 0)),
            created_at=data.get("createdAt", ""),
            end_date=data.get("endDate", ""),
            condition_id=data.get("conditionId"),
            clob_token_ids=clob_token_ids
        )


# Singleton instance
_client: Optional[PolymarketClient] = None


async def get_polymarket_client(api_key: Optional[str] = None) -> PolymarketClient:
    """Get or create Polymarket client.
    
    Args:
        api_key: Optional API key
        
    Returns:
        PolymarketClient instance
    """
    global _client
    if _client is None:
        _client = PolymarketClient(api_key=api_key)
    return _client
