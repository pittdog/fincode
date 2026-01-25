"""Fetch real historical data from Tomorrow.io and Polymarket APIs."""
import httpx
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RealHistoricalMarketData:
    """Real historical market data from Polymarket."""
    timestamp: str
    market_id: str
    city: str
    question: str
    yes_price: float
    no_price: float
    liquidity: float
    volume: float
    outcomes: List[str]


@dataclass
class RealHistoricalWeatherData:
    """Real historical weather data from Tomorrow.io."""
    timestamp: str
    city: str
    latitude: float
    longitude: float
    high_temp: float
    low_temp: float
    avg_temp: float
    condition: str
    weather_code: int


class RealHistoricalDataFetcher:
    """Fetch real historical data from APIs."""

    def __init__(
        self,
        tomorrow_io_key: str,
        polymarket_api_key: Optional[str] = None,
    ):
        """Initialize data fetcher.
        
        Args:
            tomorrow_io_key: Tomorrow.io API key
            polymarket_api_key: Optional Polymarket API key
        """
        self.tomorrow_io_key = tomorrow_io_key
        self.polymarket_api_key = polymarket_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        
        self.city_coordinates = {
            "London": {"lat": 51.5074, "lon": -0.1278},
            "New York": {"lat": 40.7128, "lon": -74.0060},
            "Seoul": {"lat": 37.5665, "lon": 126.9780},
            "Tokyo": {"lat": 35.6762, "lon": 139.6503},
            "Paris": {"lat": 48.8566, "lon": 2.3522},
        }

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def fetch_polymarket_weather_markets(
        self,
        search_query: str = "weather",
        limit: int = 100,
    ) -> List[RealHistoricalMarketData]:
        """Fetch real weather markets from Polymarket Gamma API.
        
        Args:
            search_query: Search query for markets
            limit: Number of markets to fetch
            
        Returns:
            List of real market data
        """
        try:
            logger.info(f"Fetching Polymarket markets with query: {search_query}")
            
            url = "https://gamma-api.polymarket.com/markets"
            params = {
                "search": search_query,
                "limit": limit,
                "offset": 0,
            }
            
            headers = {"Accept": "application/json"}
            if self.polymarket_api_key:
                headers["Authorization"] = f"Bearer {self.polymarket_api_key}"
            
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            markets = []
            
            # Handle both list and dict responses
            market_list = data if isinstance(data, list) else data.get("data", [])
            
            for market_data in market_list:
                try:
                    # Extract city from question
                    question = market_data.get("question", "").lower()
                    city = self._extract_city_from_question(question)
                    
                    if not city:
                        continue
                    
                    # Parse market
                    prices = market_data.get("prices", [0.5, 0.5])
                    yes_price = float(prices[0]) if prices else 0.5
                    no_price = float(prices[1]) if len(prices) > 1 else (1 - yes_price)
                    
                    market = RealHistoricalMarketData(
                        timestamp=datetime.now().isoformat(),
                        market_id=market_data.get("id", ""),
                        city=city,
                        question=market_data.get("question", ""),
                        yes_price=yes_price,
                        no_price=no_price,
                        liquidity=float(market_data.get("liquidity", 0)),
                        volume=float(market_data.get("volume24h", 0)),
                        outcomes=market_data.get("outcomes", ["Yes", "No"]),
                    )
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Error parsing market: {e}")
                    continue
            
            logger.info(f"Fetched {len(markets)} weather markets")
            return markets
        
        except Exception as e:
            logger.error(f"Error fetching Polymarket data: {e}")
            return []

    async def fetch_tomorrow_io_historical_weather(
        self,
        city: str,
        days_back: int = 7,
    ) -> List[RealHistoricalWeatherData]:
        """Fetch real historical weather data from Tomorrow.io.
        
        Note: Tomorrow.io's free tier may have limitations on historical data.
        This fetches the most recent forecast data available.
        
        Args:
            city: City name
            days_back: Number of days back to fetch (limited by API)
            
        Returns:
            List of weather data points
        """
        try:
            if city not in self.city_coordinates:
                logger.warning(f"City {city} not found in coordinates")
                return []
            
            coords = self.city_coordinates[city]
            latitude = coords["lat"]
            longitude = coords["lon"]
            
            logger.info(f"Fetching Tomorrow.io weather data for {city}")
            
            # Tomorrow.io free tier provides forecast, not historical data
            # We'll fetch the forecast for the next 7 days
            url = "https://api.tomorrow.io/v4/weather/forecast"
            
            params = {
                "location": f"{latitude},{longitude}",
                "apikey": self.tomorrow_io_key,
                "units": "fahrenheit",
                "timesteps": "1d",
            }
            
            # Build query string with fields
            fields = "temperature,temperatureMax,temperatureMin,weatherCode"
            url_with_fields = f"{url}?location={latitude},{longitude}&apikey={self.tomorrow_io_key}&timesteps=1d&fields={fields}"
            response = await self.client.get(url_with_fields)
            response.raise_for_status()
            
            data = response.json()
            weather_list = []
            
            timelines = data.get("timelines", {})
            daily = timelines.get("daily", [])
            
            for day_data in daily:
                try:
                    values = day_data.get("values", {})
                    
                    # Convert Celsius to Fahrenheit if needed
                    high_temp = float(values.get("temperatureMax", 70))
                    low_temp = float(values.get("temperatureMin", 50))
                    avg_temp = float(values.get("temperatureAvg", 60))
                    
                    weather = RealHistoricalWeatherData(
                        timestamp=day_data.get("time", ""),
                        city=city,
                        latitude=latitude,
                        longitude=longitude,
                        high_temp=high_temp,
                        low_temp=low_temp,
                        avg_temp=avg_temp,
                        condition=self._map_weather_code(values.get("weatherCodeMax", 1000)),
                        weather_code=values.get("weatherCodeMax", 1000),
                    )
                    weather_list.append(weather)
                except Exception as e:
                    logger.warning(f"Error parsing weather data: {e}")
                    continue
            
            logger.info(f"Fetched {len(weather_list)} weather data points for {city}")
            return weather_list
        
        except Exception as e:
            logger.error(f"Error fetching Tomorrow.io data for {city}: {e}")
            return []

    async def fetch_all_cities_weather(
        self,
        cities: Optional[List[str]] = None,
        days_back: int = 7,
    ) -> Dict[str, List[RealHistoricalWeatherData]]:
        """Fetch weather data for multiple cities.
        
        Args:
            cities: List of cities to fetch
            days_back: Number of days back
            
        Returns:
            Dictionary mapping city to weather data
        """
        cities = cities or list(self.city_coordinates.keys())
        weather_data = {}
        
        for city in cities:
            data = await self.fetch_tomorrow_io_historical_weather(
                city=city,
                days_back=days_back,
            )
            weather_data[city] = data
        
        return weather_data

    def _extract_city_from_question(self, question: str) -> Optional[str]:
        """Extract city name from market question.
        
        Args:
            question: Market question text
            
        Returns:
            City name or None
        """
        for city in self.city_coordinates.keys():
            if city.lower() in question.lower():
                return city
        return None

    def _map_weather_code(self, code: int) -> str:
        """Map Tomorrow.io weather code to human-readable condition.
        
        Args:
            code: Weather code
            
        Returns:
            Weather condition string
        """
        weather_map = {
            0: "Unknown",
            1000: "Clear",
            1100: "Mostly Clear",
            1101: "Partly Cloudy",
            1102: "Mostly Cloudy",
            1001: "Cloudy",
            2000: "Fog",
            2100: "Light Fog",
            4000: "Drizzle",
            4001: "Rain",
            4200: "Light Rain",
            4201: "Rain",
            5000: "Snow",
            5001: "Flurries",
            5100: "Light Snow",
            5101: "Heavy Snow",
            6000: "Freezing Drizzle",
            6001: "Freezing Rain",
            6200: "Light Freezing Rain",
            6201: "Heavy Freezing Rain",
            7000: "Ice Pellets",
            7101: "Heavy Ice Pellets",
            7102: "Light Ice Pellets",
            8000: "Thunderstorm",
        }
        return weather_map.get(code, "Unknown")


async def fetch_real_historical_data(
    tomorrow_io_key: str,
    polymarket_api_key: Optional[str] = None,
    output_dir: str = "test-results",
) -> Tuple[List[RealHistoricalMarketData], Dict[str, List[RealHistoricalWeatherData]]]:
    """Fetch real historical data from both APIs.
    
    Args:
        tomorrow_io_key: Tomorrow.io API key
        polymarket_api_key: Optional Polymarket API key
        output_dir: Directory to save data
        
    Returns:
        Tuple of (market_data, weather_data)
    """
    fetcher = RealHistoricalDataFetcher(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=polymarket_api_key,
    )
    
    try:
        # Fetch Polymarket data
        logger.info("Fetching real Polymarket data...")
        markets = await fetcher.fetch_polymarket_weather_markets(
            search_query="weather",
            limit=100,
        )
        
        # Fetch Tomorrow.io data
        logger.info("Fetching real Tomorrow.io weather data...")
        weather_data = await fetcher.fetch_all_cities_weather(
            cities=["London", "New York", "Seoul"],
            days_back=7,
        )
        
        # Save data
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save markets
        markets_file = output_path / f"real_market_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(markets_file, "w") as f:
            json.dump([asdict(m) for m in markets], f, indent=2)
        logger.info(f"Saved market data to {markets_file}")
        
        # Save weather
        weather_file = output_path / f"real_weather_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        weather_dict = {
            city: [asdict(w) for w in data]
            for city, data in weather_data.items()
        }
        with open(weather_file, "w") as f:
            json.dump(weather_dict, f, indent=2)
        logger.info(f"Saved weather data to {weather_file}")
        
        return markets, weather_data
    
    finally:
        await fetcher.close()


if __name__ == "__main__":
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    tomorrow_io_key = os.getenv("TOMORROWIO_API_KEY")
    polymarket_key = os.getenv("POLYMARKET_API_KEY")
    
    if not tomorrow_io_key:
        print("Error: TOMORROWIO_API_KEY environment variable not set")
        exit(1)
    
    markets, weather = asyncio.run(
        fetch_real_historical_data(
            tomorrow_io_key=tomorrow_io_key,
            polymarket_api_key=polymarket_key,
        )
    )
    
    print(f"\nFetched {len(markets)} markets")
    print(f"Fetched weather data for {len(weather)} cities")
