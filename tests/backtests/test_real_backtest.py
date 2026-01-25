"""Real backtest tests using actual API data from Polymarket and Tomorrow.io."""
import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock

from utils.real_historical_data import (
    RealHistoricalDataFetcher,
    RealHistoricalMarketData,
    RealHistoricalWeatherData,
)
from utils.real_backtest_util import (
    RealBacktestEngine,
    RealBacktestReporter,
)


class TestRealHistoricalDataFetcher:
    """Tests for real historical data fetching."""

    @pytest.mark.asyncio
    async def test_fetcher_initialization(self):
        """Test fetcher initialization."""
        fetcher = RealHistoricalDataFetcher(
            tomorrow_io_key="test_key",
            polymarket_api_key="test_pm_key",
        )
        assert fetcher.tomorrow_io_key == "test_key"
        assert fetcher.polymarket_api_key == "test_pm_key"
        assert "London" in fetcher.city_coordinates
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_city_coordinates_available(self):
        """Test that city coordinates are available."""
        fetcher = RealHistoricalDataFetcher(tomorrow_io_key="test_key")
        
        cities = ["London", "New York", "Seoul", "Tokyo", "Paris"]
        for city in cities:
            assert city in fetcher.city_coordinates
            coords = fetcher.city_coordinates[city]
            assert "lat" in coords
            assert "lon" in coords
            assert isinstance(coords["lat"], float)
            assert isinstance(coords["lon"], float)
        
        await fetcher.close()

    def test_extract_city_from_question(self):
        """Test city extraction from market question."""
        fetcher = RealHistoricalDataFetcher(tomorrow_io_key="test_key")
        
        test_cases = [
            ("Will London temperature exceed 75°F?", "London"),
            ("New York weather forecast", "New York"),
            ("Seoul temperature prediction", "Seoul"),
            ("Random market question", None),
        ]
        
        for question, expected_city in test_cases:
            city = fetcher._extract_city_from_question(question)
            assert city == expected_city

    def test_weather_code_mapping(self):
        """Test weather code to condition mapping."""
        fetcher = RealHistoricalDataFetcher(tomorrow_io_key="test_key")
        
        test_cases = [
            (1000, "Clear"),
            (1001, "Cloudy"),
            (4000, "Drizzle"),
            (4001, "Rain"),
            (5000, "Snow"),
            (8000, "Thunderstorm"),
        ]
        
        for code, expected_condition in test_cases:
            condition = fetcher._map_weather_code(code)
            assert condition == expected_condition

    @pytest.mark.asyncio
    async def test_fetch_polymarket_weather_markets_mock(self):
        """Test Polymarket market fetching with mock data."""
        fetcher = RealHistoricalDataFetcher(tomorrow_io_key="test_key")
        
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "market_1",
                "question": "Will London temperature exceed 75°F?",
                "prices": [0.08, 0.92],
                "liquidity": 150.0,
                "volume24h": 500.0,
                "outcomes": ["Yes", "No"],
            },
            {
                "id": "market_2",
                "question": "Will New York temperature exceed 70°F?",
                "prices": [0.06, 0.94],
                "liquidity": 100.0,
                "volume24h": 300.0,
                "outcomes": ["Yes", "No"],
            },
        ]
        
        async def mock_get(*args, **kwargs):
            return mock_response
        
        with patch.object(fetcher.client, "get", side_effect=mock_get):
            markets = await fetcher.fetch_polymarket_weather_markets(
                search_query="weather",
                limit=100,
            )
        
        assert len(markets) == 2
        assert all(isinstance(m, RealHistoricalMarketData) for m in markets)
        assert markets[0].city == "London"
        assert markets[1].city == "New York"
        
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_fetch_tomorrow_io_weather_mock(self):
        """Test Tomorrow.io weather fetching with mock data."""
        fetcher = RealHistoricalDataFetcher(tomorrow_io_key="test_key")
        
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "timelines": {
                "daily": [
                    {
                        "time": "2026-01-25T06:00:00Z",
                        "values": {
                            "temperatureMax": 45.0,
                            "temperatureMin": 35.0,
                            "temperatureAvg": 40.0,
                            "weatherCodeMax": 1001,
                        },
                    },
                    {
                        "time": "2026-01-26T06:00:00Z",
                        "values": {
                            "temperatureMax": 48.0,
                            "temperatureMin": 38.0,
                            "temperatureAvg": 43.0,
                            "weatherCodeMax": 1000,
                        },
                    },
                ]
            }
        }
        
        async def mock_get(*args, **kwargs):
            return mock_response
        
        with patch.object(fetcher.client, "get", side_effect=mock_get):
            weather = await fetcher.fetch_tomorrow_io_historical_weather(
                city="London",
                days_back=7,
            )
        
        assert len(weather) == 2
        assert all(isinstance(w, RealHistoricalWeatherData) for w in weather)
        assert weather[0].city == "London"
        assert weather[0].high_temp == 45.0
        assert weather[0].low_temp == 35.0
        
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_fetch_all_cities_weather_mock(self):
        """Test fetching weather for multiple cities."""
        fetcher = RealHistoricalDataFetcher(tomorrow_io_key="test_key")
        
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "timelines": {
                "daily": [
                    {
                        "time": "2026-01-25T06:00:00Z",
                        "values": {
                            "temperatureMax": 45.0,
                            "temperatureMin": 35.0,
                            "temperatureAvg": 40.0,
                            "weatherCodeMax": 1001,
                        },
                    }
                ]
            }
        }
        
        async def mock_get(*args, **kwargs):
            return mock_response
        
        with patch.object(fetcher.client, "get", side_effect=mock_get):
            weather_data = await fetcher.fetch_all_cities_weather(
                cities=["London", "New York"],
            )
        
        assert "London" in weather_data
        assert "New York" in weather_data
        assert len(weather_data["London"]) > 0
        assert len(weather_data["New York"]) > 0
        
        await fetcher.close()


class TestRealBacktestEngine:
    """Tests for real backtest engine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = RealBacktestEngine()
        assert engine.strategy is not None
        assert engine.strategy.min_liquidity == 50.0

    def test_run_backtest_with_real_data_structure(self):
        """Test backtest with real data structure."""
        # Create sample real market data
        markets = [
            RealHistoricalMarketData(
                timestamp="2026-01-25T06:00:00Z",
                market_id="market_1",
                city="London",
                question="Will London temperature exceed 75°F?",
                yes_price=0.08,
                no_price=0.92,
                liquidity=150.0,
                volume=500.0,
                outcomes=["Yes", "No"],
            ),
            RealHistoricalMarketData(
                timestamp="2026-01-25T06:00:00Z",
                market_id="market_2",
                city="New York",
                question="Will New York temperature exceed 70°F?",
                yes_price=0.06,
                no_price=0.94,
                liquidity=100.0,
                volume=300.0,
                outcomes=["Yes", "No"],
            ),
        ]
        
        # Create sample weather data
        weather_data = {
            "London": [
                RealHistoricalWeatherData(
                    timestamp="2026-01-25T06:00:00Z",
                    city="London",
                    latitude=51.5074,
                    longitude=-0.1278,
                    high_temp=45.0,
                    low_temp=35.0,
                    avg_temp=40.0,
                    condition="Cloudy",
                    weather_code=1001,
                ),
            ],
            "New York": [
                RealHistoricalWeatherData(
                    timestamp="2026-01-25T06:00:00Z",
                    city="New York",
                    latitude=40.7128,
                    longitude=-74.0060,
                    high_temp=48.0,
                    low_temp=38.0,
                    avg_temp=43.0,
                    condition="Clear",
                    weather_code=1000,
                ),
            ],
        }
        
        # Run backtest
        engine = RealBacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather_data,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Verify results structure
        assert "backtest_info" in results
        assert "data_points" in results
        assert "trading_results" in results
        assert "strategy_parameters" in results
        assert "market_sample" in results
        
        # Verify backtest info
        assert results["backtest_info"]["data_source"] == "Real API Data (Polymarket + Tomorrow.io)"
        assert results["backtest_info"]["markets_analyzed"] == 2
        
        # Verify data points
        assert results["data_points"]["markets_analyzed"] == 2

    def test_backtest_results_structure(self):
        """Test backtest results have correct structure."""
        markets = [
            RealHistoricalMarketData(
                timestamp="2026-01-25T06:00:00Z",
                market_id="market_1",
                city="London",
                question="Will London temperature exceed 75°F?",
                yes_price=0.08,
                no_price=0.92,
                liquidity=150.0,
                volume=500.0,
                outcomes=["Yes", "No"],
            ),
        ]
        
        weather_data = {
            "London": [
                RealHistoricalWeatherData(
                    timestamp="2026-01-25T06:00:00Z",
                    city="London",
                    latitude=51.5074,
                    longitude=-0.1278,
                    high_temp=45.0,
                    low_temp=35.0,
                    avg_temp=40.0,
                    condition="Cloudy",
                    weather_code=1001,
                ),
            ],
        }
        
        engine = RealBacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather_data,
            initial_capital=197.0,
        )
        
        # Check trading results
        tr = results["trading_results"]
        assert tr["initial_capital"] == 197.0
        assert tr["final_capital"] >= tr["initial_capital"]
        assert "roi_percentage" in tr
        assert "win_rate" in tr


class TestRealBacktestReporter:
    """Tests for real backtest reporting."""

    def test_generate_report_with_real_data(self):
        """Test report generation with real data structure."""
        results = {
            "backtest_info": {
                "timestamp": "2026-01-25T06:00:00Z",
                "data_source": "Real API Data (Polymarket + Tomorrow.io)",
                "markets_analyzed": 10,
                "cities_covered": ["London", "New York", "Seoul"],
            },
            "data_points": {
                "markets_analyzed": 10,
                "opportunities_identified": 5,
                "buy_signals": 2,
            },
            "trading_results": {
                "trades_executed": 2,
                "initial_capital": 197.0,
                "final_capital": 500.0,
                "total_profit": 303.0,
                "roi_percentage": 153.8,
                "winning_trades": 2,
                "losing_trades": 0,
                "win_rate": 100.0,
            },
            "strategy_parameters": {
                "min_liquidity": 50.0,
                "min_edge": 0.15,
                "max_price": 0.10,
                "min_confidence": 0.60,
            },
            "market_sample": [
                {
                    "city": "London",
                    "question": "Will London temperature exceed 75°F?",
                    "yes_price": 0.08,
                    "liquidity": 150.0,
                },
            ],
        }
        
        report = RealBacktestReporter.generate_report(results)
        
        assert "POLYMARKET REAL DATA BACKTEST REPORT" in report
        assert "Real API Data" in report
        assert "London" in report
        assert "197.00" in report
        assert "500.00" in report
        assert "153.80" in report

    def test_report_contains_all_sections(self):
        """Test report contains all required sections."""
        results = {
            "backtest_info": {
                "timestamp": "2026-01-25T06:00:00Z",
                "data_source": "Real API Data",
                "markets_analyzed": 10,
                "cities_covered": ["London"],
            },
            "data_points": {
                "markets_analyzed": 10,
                "opportunities_identified": 5,
                "buy_signals": 2,
            },
            "trading_results": {
                "trades_executed": 2,
                "initial_capital": 197.0,
                "final_capital": 500.0,
                "total_profit": 303.0,
                "roi_percentage": 153.8,
                "winning_trades": 2,
                "losing_trades": 0,
                "win_rate": 100.0,
            },
            "strategy_parameters": {
                "min_liquidity": 50.0,
                "min_edge": 0.15,
                "max_price": 0.10,
                "min_confidence": 0.60,
            },
            "market_sample": [],
        }
        
        report = RealBacktestReporter.generate_report(results)
        
        assert "BACKTEST INFORMATION" in report
        assert "DATA ANALYSIS" in report
        assert "TRADING RESULTS" in report
        assert "STRATEGY PARAMETERS" in report


class TestRealBacktestIntegration:
    """Integration tests for real backtest workflow."""

    def test_end_to_end_real_backtest_workflow(self):
        """Test complete real backtest workflow."""
        # Create realistic market and weather data
        markets = [
            RealHistoricalMarketData(
                timestamp="2026-01-25T06:00:00Z",
                market_id=f"market_{i}",
                city=["London", "New York", "Seoul"][i % 3],
                question=f"Will {['London', 'New York', 'Seoul'][i % 3]} temperature exceed 75°F?",
                yes_price=0.05 + (i % 10) * 0.01,
                no_price=0.95 - (i % 10) * 0.01,
                liquidity=100.0 + i * 10,
                volume=500.0 + i * 50,
                outcomes=["Yes", "No"],
            )
            for i in range(20)
        ]
        
        weather_data = {
            "London": [
                RealHistoricalWeatherData(
                    timestamp="2026-01-25T06:00:00Z",
                    city="London",
                    latitude=51.5074,
                    longitude=-0.1278,
                    high_temp=45.0,
                    low_temp=35.0,
                    avg_temp=40.0,
                    condition="Cloudy",
                    weather_code=1001,
                ),
            ],
            "New York": [
                RealHistoricalWeatherData(
                    timestamp="2026-01-25T06:00:00Z",
                    city="New York",
                    latitude=40.7128,
                    longitude=-74.0060,
                    high_temp=48.0,
                    low_temp=38.0,
                    avg_temp=43.0,
                    condition="Clear",
                    weather_code=1000,
                ),
            ],
            "Seoul": [
                RealHistoricalWeatherData(
                    timestamp="2026-01-25T06:00:00Z",
                    city="Seoul",
                    latitude=37.5665,
                    longitude=126.9780,
                    high_temp=32.0,
                    low_temp=22.0,
                    avg_temp=27.0,
                    condition="Cloudy",
                    weather_code=1001,
                ),
            ],
        }
        
        # Run backtest
        engine = RealBacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather_data,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Generate report
        report = RealBacktestReporter.generate_report(results)
        
        # Verify complete workflow
        assert results["backtest_info"]["markets_analyzed"] == 20
        assert "POLYMARKET REAL DATA BACKTEST REPORT" in report
        assert len(report) > 500  # Report should be substantial


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
