"""Tests for Tomorrow.io Weather API integration."""
import pytest
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to sys.path
root_path = Path(__file__).parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

from agent.tools.weather_tool import WeatherClient
from tests.test_utils import save_test_result

class TestTomorrowAPI:
    """Integration tests for Tomorrow.io API."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("TOMORROWIO_API_KEY"), reason="TOMORROWIO_API_KEY not set")
    async def test_live_fetch_forecast(self):
        """Fetch real HOURLY weather forecast with F and C units."""
        client = WeatherClient(api_key=os.getenv("TOMORROWIO_API_KEY"))
        forecast = await client.get_forecast("London")
        
        assert forecast is not None
        assert forecast.hourly_data is not None
        assert forecast.avg_temp_c is not None # Verify C conversion
        save_test_result("live_weather_forecast_hourly", forecast)
        await client.close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("TOMORROWIO_API_KEY"), reason="TOMORROWIO_API_KEY not set")
    async def test_multiple_cities_forecast(self):
        """Test fetching forecasts for multiple major cities."""
        client = WeatherClient(api_key=os.getenv("TOMORROWIO_API_KEY"))
        cities = ["New York", "Seoul"]
        
        for city in cities:
            forecast = await client.get_forecast(city)
            assert forecast is not None
            assert forecast.city == city
            print(f"Fetched forecast for {city}: {forecast.avg_temp_c}°C")
            
        await client.close()
