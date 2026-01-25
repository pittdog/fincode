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
    ) -> List[PolymarketMarket]:
        """Fetch markets from Polymarket.
        
        Args:
            search: Search query for market filtering
            limit: Number of markets to return
            offset: Pagination offset
            sort_by: Sort field (volume, liquidity, created_at)
            
        Returns:
            List of PolymarketMarket objects
        """
        try:
            params = {
                "limit": limit,
                "offset": offset,
                "sortBy": sort_by,
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

            markets = []
            for market_data in data.get("data", []):
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
