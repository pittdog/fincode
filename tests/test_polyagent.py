"""Tests for Polymarket trading agent."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from agent.tools.polymarket_tool import PolymarketClient, PolymarketMarket
from agent.tools.weather_tool import WeatherClient, WeatherForecast
from agent.tools.trading_strategy import (
    TradingStrategy,
    TradeSignal,
    TradeOpportunity,
    PortfolioSimulator,
)


class TestPolymarketClient:
    """Tests for Polymarket client."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = PolymarketClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.BASE_URL == "https://gamma-api.polymarket.com"
        await client.close()

    @pytest.mark.asyncio
    async def test_parse_market(self):
        """Test market parsing."""
        client = PolymarketClient()
        
        market_data = {
            "id": "test_market_1",
            "question": "Will London temperature exceed 75°F?",
            "description": "Weather market for London",
            "outcomes": ["Yes", "No"],
            "prices": [0.45, 0.55],
            "liquidity": 150.0,
            "volume24h": 500.0,
            "createdAt": "2024-01-01T00:00:00Z",
            "endDate": "2024-02-01T00:00:00Z",
        }
        
        market = client._parse_market(market_data)
        
        assert market.id == "test_market_1"
        assert market.yes_price == 0.45
        assert market.no_price == 0.55
        assert market.liquidity == 150.0
        assert market.volume == 500.0
        
        await client.close()

    @pytest.mark.asyncio
    async def test_search_weather_markets(self):
        """Test weather market search."""
        client = PolymarketClient()
        
        # Mock the get_markets method
        mock_markets = [
            PolymarketMarket(
                id="market_1",
                question="Will London temperature exceed 75°F?",
                description="London weather",
                outcomes=["Yes", "No"],
                yes_price=0.08,
                no_price=0.92,
                liquidity=100.0,
                volume=500.0,
                created_at="2024-01-01",
                end_date="2024-02-01",
            )
        ]
        
        with patch.object(client, 'get_markets', return_value=mock_markets):
            markets = await client.search_weather_markets(
                cities=["London"],
                min_liquidity=50.0,
                max_price=0.10,
            )
            
            assert len(markets) > 0
        
        await client.close()


class TestWeatherClient:
    """Tests for weather client."""

    def test_client_initialization(self):
        """Test weather client initialization."""
        client = WeatherClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert "London" in client.city_coordinates

    def test_city_coordinates(self):
        """Test city coordinates."""
        client = WeatherClient(api_key="test_key")
        
        assert client.city_coordinates["London"]["lat"] == 51.5074
        assert client.city_coordinates["New York"]["lat"] == 40.7128
        assert client.city_coordinates["Seoul"]["lat"] == 37.5665

    def test_calculate_probability(self):
        """Test probability calculation."""
        client = WeatherClient(api_key="test_key")
        
        # Test within deviation
        prob = client.calculate_probability(70.0, 70.0, 3.5)
        assert prob == 1.0
        
        # Test at edge of deviation
        prob = client.calculate_probability(73.5, 70.0, 3.5)
        assert 0.5 < prob < 1.0  # At edge should be between 0.5 and 1.0
        
        # Test outside deviation
        prob = client.calculate_probability(80.0, 70.0, 3.5)
        assert prob < 0.5

    def test_weather_code_mapping(self):
        """Test weather code mapping."""
        client = WeatherClient(api_key="test_key")
        
        assert client._map_weather_code(1000) == "Clear"
        assert client._map_weather_code(1001) == "Cloudy"
        assert client._map_weather_code(4001) == "Rain"
        assert client._map_weather_code(5000) == "Snow"
        assert client._map_weather_code(0) == "Unknown"

    def test_parse_forecast(self):
        """Test forecast parsing."""
        client = WeatherClient(api_key="test_key")
        
        forecast_data = {
            "timelines": {
                "daily": [
                    {
                        "time": "2024-01-25T00:00:00Z",
                        "values": {
                            "temperatureMax": 75.0,
                            "temperatureMin": 55.0,
                            "temperature": 65.0,
                            "weatherCode": 1000,
                        }
                    }
                ]
            }
        }
        
        forecast = client._parse_forecast(forecast_data, "London", 51.5074, -0.1278)
        
        assert forecast is not None
        assert forecast.city == "London"
        assert forecast.high_temp == 75.0
        assert forecast.low_temp == 55.0
        assert forecast.avg_temp == 65.0
        assert forecast.condition == "Clear"


class TestTradingStrategy:
    """Tests for trading strategy."""

    def test_strategy_initialization(self):
        """Test strategy initialization."""
        strategy = TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        
        assert strategy.min_liquidity == 50.0
        assert strategy.min_edge == 0.15
        assert strategy.max_price == 0.10
        assert strategy.min_confidence == 0.60

    def test_analyze_market_buy_signal(self):
        """Test market analysis for BUY signal."""
        strategy = TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        
        # Market price: $0.04, Fair price: $0.06 = 50% edge
        opportunity = strategy.analyze_market(
            market_id="test_1",
            city="London",
            market_question="Will London temperature exceed 75°F?",
            market_price=0.04,
            fair_price=0.06,
            liquidity=100.0,
        )
        
        assert opportunity.signal == TradeSignal.BUY
        assert abs(opportunity.edge_percentage - 0.5) < 0.01  # Allow for floating point errors
        assert opportunity.confidence > 0.6

    def test_analyze_market_sell_signal(self):
        """Test market analysis for SELL signal."""
        strategy = TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        
        # Market price: $0.08, Fair price: $0.05 = -37.5% edge
        opportunity = strategy.analyze_market(
            market_id="test_2",
            city="New York",
            market_question="Will New York temperature exceed 75°F?",
            market_price=0.08,
            fair_price=0.05,
            liquidity=100.0,
        )
        
        assert opportunity.signal == TradeSignal.SELL
        assert opportunity.edge_percentage < 0

    def test_analyze_market_skip_low_liquidity(self):
        """Test market analysis skips low liquidity."""
        strategy = TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        
        opportunity = strategy.analyze_market(
            market_id="test_3",
            city="Seoul",
            market_question="Will Seoul temperature exceed 75°F?",
            market_price=0.04,
            fair_price=0.06,
            liquidity=20.0,  # Below minimum
        )
        
        assert opportunity.signal == TradeSignal.SKIP

    def test_analyze_market_skip_high_price(self):
        """Test market analysis skips high price."""
        strategy = TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        
        opportunity = strategy.analyze_market(
            market_id="test_4",
            city="London",
            market_question="Will London temperature exceed 75°F?",
            market_price=0.15,  # Above maximum
            fair_price=0.20,
            liquidity=100.0,
        )
        
        assert opportunity.signal == TradeSignal.SKIP

    def test_rank_opportunities(self):
        """Test opportunity ranking."""
        strategy = TradingStrategy()
        
        opportunities = [
            TradeOpportunity(
                market_id="1",
                city="London",
                market_question="Q1",
                market_price=0.04,
                fair_price=0.06,
                edge_percentage=0.5,
                signal=TradeSignal.BUY,
                confidence=0.8,
                liquidity=100.0,
                reasoning="Test 1",
            ),
            TradeOpportunity(
                market_id="2",
                city="New York",
                market_question="Q2",
                market_price=0.05,
                fair_price=0.08,
                edge_percentage=0.6,
                signal=TradeSignal.BUY,
                confidence=0.9,
                liquidity=200.0,
                reasoning="Test 2",
            ),
        ]
        
        ranked = strategy.rank_opportunities(opportunities)
        
        # Higher edge and confidence should rank higher
        assert ranked[0].edge_percentage >= ranked[1].edge_percentage or \
               ranked[0].confidence >= ranked[1].confidence

    def test_filter_opportunities(self):
        """Test opportunity filtering."""
        strategy = TradingStrategy()
        
        opportunities = [
            TradeOpportunity(
                market_id="1",
                city="London",
                market_question="Q1",
                market_price=0.04,
                fair_price=0.06,
                edge_percentage=0.5,
                signal=TradeSignal.BUY,
                confidence=0.8,
                liquidity=100.0,
                reasoning="Test 1",
            ),
            TradeOpportunity(
                market_id="2",
                city="New York",
                market_question="Q2",
                market_price=0.05,
                fair_price=0.04,
                edge_percentage=-0.2,
                signal=TradeSignal.SELL,
                confidence=0.7,
                liquidity=100.0,
                reasoning="Test 2",
            ),
        ]
        
        buy_only = strategy.filter_opportunities(opportunities, TradeSignal.BUY)
        assert len(buy_only) == 1
        assert buy_only[0].signal == TradeSignal.BUY


class TestPortfolioSimulator:
    """Tests for portfolio simulator."""

    def test_simulator_initialization(self):
        """Test simulator initialization."""
        sim = PortfolioSimulator(initial_capital=197.0)
        
        assert sim.initial_capital == 197.0
        assert sim.current_capital == 197.0
        assert len(sim.trades) == 0
        assert sim.total_roi == 0.0

    def test_execute_trade_success(self):
        """Test successful trade execution."""
        sim = PortfolioSimulator(initial_capital=197.0)
        
        opportunity = TradeOpportunity(
            market_id="1",
            city="London",
            market_question="Q1",
            market_price=0.04,
            fair_price=0.06,
            edge_percentage=0.5,
            signal=TradeSignal.BUY,
            confidence=0.8,
            liquidity=100.0,
            reasoning="Test",
        )
        
        result = sim.execute_trade(opportunity, 100.0)
        
        assert result["success"] is True
        assert "trade" in result
        assert len(sim.trades) == 1
        assert sim.current_capital > 197.0  # Profit from 50% edge

    def test_execute_trade_insufficient_capital(self):
        """Test trade execution with insufficient capital."""
        sim = PortfolioSimulator(initial_capital=50.0)
        
        opportunity = TradeOpportunity(
            market_id="1",
            city="London",
            market_question="Q1",
            market_price=0.04,
            fair_price=0.06,
            edge_percentage=0.5,
            signal=TradeSignal.BUY,
            confidence=0.8,
            liquidity=100.0,
            reasoning="Test",
        )
        
        result = sim.execute_trade(opportunity, 100.0)
        
        assert result["success"] is False
        assert "Insufficient capital" in result["reason"]

    def test_portfolio_summary(self):
        """Test portfolio summary."""
        sim = PortfolioSimulator(initial_capital=197.0)
        
        opportunity = TradeOpportunity(
            market_id="1",
            city="London",
            market_question="Q1",
            market_price=0.04,
            fair_price=0.06,
            edge_percentage=0.5,
            signal=TradeSignal.BUY,
            confidence=0.8,
            liquidity=100.0,
            reasoning="Test",
        )
        
        sim.execute_trade(opportunity, 100.0)
        
        summary = sim.get_summary()
        
        assert summary["initial_capital"] == 197.0
        assert summary["num_trades"] == 1
        assert summary["winning_trades"] == 1
        assert summary["current_capital"] > summary["initial_capital"]

    def test_multiple_trades_simulation(self):
        """Test multiple trades simulation."""
        sim = PortfolioSimulator(initial_capital=1000.0)
        
        opportunities = [
            TradeOpportunity(
                market_id=str(i),
                city="London",
                market_question=f"Q{i}",
                market_price=0.04,
                fair_price=0.06,
                edge_percentage=0.5,
                signal=TradeSignal.BUY,
                confidence=0.8,
                liquidity=100.0,
                reasoning=f"Test {i}",
            )
            for i in range(5)
        ]
        
        for opp in opportunities:
            sim.execute_trade(opp, 100.0)
        
        summary = sim.get_summary()
        
        assert summary["num_trades"] == 5
        assert summary["winning_trades"] == 5
        assert summary["current_capital"] > 1000.0


class TestIntegration:
    """Integration tests."""

    def test_end_to_end_analysis(self):
        """Test end-to-end market analysis."""
        strategy = TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        
        # Create mock markets
        markets = [
            PolymarketMarket(
                id="market_1",
                question="Will London temperature exceed 75°F?",
                description="London weather",
                outcomes=["Yes", "No"],
                yes_price=0.04,
                no_price=0.96,
                liquidity=100.0,
                volume=500.0,
                created_at="2024-01-01",
                end_date="2024-02-01",
            ),
            PolymarketMarket(
                id="market_2",
                question="Will New York temperature exceed 75°F?",
                description="New York weather",
                outcomes=["Yes", "No"],
                yes_price=0.08,
                no_price=0.92,
                liquidity=80.0,
                volume=400.0,
                created_at="2024-01-01",
                end_date="2024-02-01",
            ),
        ]
        
        # Analyze markets
        opportunities = []
        for market in markets:
            opp = strategy.analyze_market(
                market_id=market.id,
                city="London" if "London" in market.question else "New York",
                market_question=market.question,
                market_price=market.yes_price,
                fair_price=0.06,  # Mock fair price
                liquidity=market.liquidity,
            )
            opportunities.append(opp)
        
        # Verify analysis
        assert len(opportunities) == 2
        assert any(opp.signal == TradeSignal.BUY for opp in opportunities)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
