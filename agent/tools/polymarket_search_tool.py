"""Tool for searching weather markets on Polymarket with deep CLOB integration."""
import logging
import re
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from .polymarket_tool import PolymarketClient, PolymarketMarket
from .polymarket_clob_api import PolymarketCLOBClient
from .weather_tool import WeatherClient

logger = logging.getLogger(__name__)

class WeatherSearchTool:
    """Tool for targeted searching of weather-related markets with order book details."""

    WEATHER_KEYWORDS = [
        "temperature", "weather", "rain", "snow", "degree", 
        "celsius", "fahrenheit", "heat", "cold", "climate"
    ]
    
    CITY_PATTERNS = [
        "London", "New York", "Seoul", "Tokyo", "Paris", 
        "Singapore", "Hong Kong", "Dubai", "NYC"
    ]

    def __init__(self, client: Optional[PolymarketClient] = None, clob_client: Optional[PolymarketCLOBClient] = None, weather_client: Optional[WeatherClient] = None):
        self.client = client
        self.clob_client = clob_client
        self.weather_client = weather_client

    async def _setup_clients(self):
        if self.client is None:
            from .polymarket_tool import get_polymarket_client
            self.client = await get_polymarket_client()
        if self.clob_client is None:
            self.clob_client = PolymarketCLOBClient(key=os.getenv("POLYMARKET_PRIVATE_KEY"))
        if self.weather_client is None:
            tomorrow_key = os.getenv("TOMORROWIO_API_KEY")
            if tomorrow_key:
                self.weather_client = WeatherClient(api_key=tomorrow_key)

    def _extract_city(self, question: str) -> Optional[str]:
        """Extract city name from market question (case-insensitive)."""
        question_lower = question.lower()
        for city in self.CITY_PATTERNS:
            if city.lower() in question_lower:
                # Convert NYC to New York
                if city.upper() == "NYC":
                    return "New York"
                return city  # Return the properly capitalized version
        return None

    def _extract_temp_from_question(self, question: str) -> Optional[float]:
        """Extract temperature value from question (e.g., '75°F' or '5°C')."""
        # Try Celsius pattern first
        celsius_match = re.search(r'(\d+)°?C', question)
        if celsius_match:
            return float(celsius_match.group(1))
        
        # Try Fahrenheit pattern
        fahrenheit_match = re.search(r'(\d+)°?F', question)
        if fahrenheit_match:
            # Convert to Celsius
            f_temp = float(fahrenheit_match.group(1))
            return (f_temp - 32) * 5/9
        
        return None

    async def _get_forecast_at_time(self, city: str, target_time: str) -> Optional[Dict[str, Any]]:
        """Get weather forecast for a specific time."""
        if not self.weather_client:
            return None
        
        try:
            # Fetch full forecast
            forecast = await self.weather_client.get_forecast(city)
            if not forecast or not forecast.hourly_data:
                return None
            
            # Parse target time
            target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
            
            # Find closest hourly forecast
            closest_forecast = None
            min_diff = float('inf')
            
            for hour in forecast.hourly_data:
                hour_time = datetime.fromisoformat(hour['time'].replace('Z', '+00:00'))
                diff = abs((target_dt - hour_time).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_forecast = hour
            
            if closest_forecast:
                # Tomorrow.io returns Fahrenheit with imperial units
                temp_f = closest_forecast['values'].get('temperature', 0)
                temp_c = (temp_f - 32) * 5 / 9
                
                return {
                    "temperature_c": round(temp_c, 1),
                    "temperature_f": round(temp_f, 1),
                    "time": closest_forecast['time']
                }
        except Exception  as e:
            logger.error(f"Error fetching forecast for {city} at {target_time}: {e}")
        
        return None

    async def search(
        self, 
        query: str = "temperature", 
        city: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for weather markets and enrich with detailed CLOB order book data.
        
        Args:
            query: Search query
            city: Optional city filter (case-insensitive)
            limit: Max results
            
        Returns:
            List of markets with question, ID, detailed bid/ask info, resolution time, and forecast
        """
        await self._setup_clients()
        
        # Normalize city to title case for consistency
        if city:
            city = city.title()
        
        search_query = query
        if city:
            search_query = f"{query} {city}"
            
        # 1. Search Gamma (Public Search)
        markets = await self.client.gamma_search(q=search_query, limit=limit)
        logger.info(f"Gamma search for '{search_query}' returned {len(markets)} markets")
        
        # Cache forecasts per city to avoid rate limiting
        forecast_cache = {}
        
        results = []
        for m in markets:
            # 2. Verify it's actually weather related
            q_lower = m.question.lower()
            if not any(kw in q_lower for kw in self.WEATHER_KEYWORDS):
                continue
            
            # 3. Get CLOB Order Book for YES/NO tokens
            yes_book = None
            no_book = None
            
            if m.clob_token_ids and len(m.clob_token_ids) >= 2:
                # Fetch YES token (index 0)
                yes_token_id = m.clob_token_ids[0]
                yes_book = await self.clob_client.get_order_book(yes_token_id, question=m.question)
                
                # Fetch NO token (index 1)
                no_token_id = m.clob_token_ids[1]
                no_book = await self.clob_client.get_order_book(no_token_id, question=m.question)
            
            # 4. Extract city and get forecast at resolution time (with caching)
            market_city = self._extract_city(m.question) if not city else city
            forecast_at_resolution = None
            
            if market_city and m.end_date and self.weather_client:
                # Check cache first
                cache_key = f"{market_city}:{m.end_date}"
                if cache_key in forecast_cache:
                    forecast_at_resolution = forecast_cache[cache_key]
                else:
                    forecast_at_resolution = await self._get_forecast_at_time(market_city, m.end_date)
                    # Cache for reuse (even if None to avoid retrying failed fetches)
                    forecast_cache[cache_key] = forecast_at_resolution

            results.append({
                "id": m.id,
                "question": m.question,
                "liquidity": m.liquidity,
                "volume": m.volume,
                "yes_price": m.yes_price,
                "no_price": m.no_price,
                "end_date": m.end_date,
                "yes_book": {
                    "best_bid": yes_book.best_bid if yes_book else None,
                    "best_ask": yes_book.best_ask if yes_book else None,
                    "spread": yes_book.spread if yes_book else None,
                    "token_id": m.clob_token_ids[0] if m.clob_token_ids else None
                } if yes_book else {},
                "no_book": {
                    "best_bid": no_book.best_bid if no_book else None,
                    "best_ask": no_book.best_ask if no_book else None,
                    "spread": no_book.spread if no_book else None,
                    "token_id": m.clob_token_ids[1] if len(m.clob_token_ids) > 1 else None
                } if no_book else {},
                "forecast_at_resolution": forecast_at_resolution,
                "market_city": market_city
            })

        # Sort by liquidity for better quality
        logger.info(f"Processed {len(results)} weather markets. Forecast cache entries: {len(forecast_cache)}")
        return sorted(results, key=lambda x: x["liquidity"], reverse=True)
