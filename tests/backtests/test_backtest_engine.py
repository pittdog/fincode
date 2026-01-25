"""Backtest tests for Polymarket trading strategy with historical data simulation."""
import pytest
from datetime import datetime, timedelta

from utils.polymarket_backtest_util import (
    BacktestDataGenerator,
    BacktestEngine,
    BacktestReporter,
    HistoricalMarketData,
    HistoricalWeatherData,
)
from agent.tools.trading_strategy import TradingStrategy, TradeSignal


class TestBacktestDataGenerator:
    """Tests for historical data generation."""

    def test_generate_market_data(self):
        """Test market data generation."""
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=50,
            days=30,
        )
        
        assert len(markets) == 50
        assert all(isinstance(m, HistoricalMarketData) for m in markets)
        assert all(0.03 <= m.yes_price <= 0.10 for m in markets)
        assert all(m.liquidity >= 50 for m in markets)
        assert all(m.city in ["London", "New York", "Seoul"] for m in markets)

    def test_generate_weather_data(self):
        """Test weather data generation."""
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=50,
            days=30,
        )
        
        assert len(weather) == 50
        assert all(isinstance(w, HistoricalWeatherData) for w in weather)
        assert all(w.city in ["London", "New York", "Seoul"] for w in weather)
        # High temp should be >= low temp (allowing for edge cases)
        assert all(w.high_temp >= w.low_temp for w in weather)

    def test_market_data_temporal_distribution(self):
        """Test that market data is distributed over time."""
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=100,
            days=30,
        )
        
        timestamps = [m.timestamp for m in markets]
        unique_dates = set(ts[:10] for ts in timestamps)
        
        # Should span multiple days
        assert len(unique_dates) > 1

    def test_weather_data_city_distribution(self):
        """Test weather data covers all cities."""
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=100,
            days=30,
        )
        
        cities = set(w.city for w in weather)
        assert "London" in cities
        assert "New York" in cities
        assert "Seoul" in cities


class TestBacktestEngine:
    """Tests for backtest engine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = BacktestEngine()
        assert engine.strategy is not None
        assert engine.strategy.min_liquidity == 50.0
        assert engine.strategy.min_edge == 0.15

    def test_engine_with_custom_strategy(self):
        """Test engine with custom strategy."""
        strategy = TradingStrategy(
            min_liquidity=100.0,
            min_edge=0.20,
            max_price=0.05,
            min_confidence=0.70,
        )
        engine = BacktestEngine(strategy=strategy)
        
        assert engine.strategy.min_liquidity == 100.0
        assert engine.strategy.min_edge == 0.20

    def test_run_backtest_basic(self):
        """Test basic backtest execution."""
        # Generate data
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=50,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=50,
            days=30,
        )
        
        # Run backtest
        engine = BacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Verify results structure
        assert "backtest_period" in results
        assert "data_points" in results
        assert "trading_results" in results
        assert "strategy_parameters" in results

    def test_backtest_results_content(self):
        """Test backtest results contain expected data."""
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=100,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=100,
            days=30,
        )
        
        engine = BacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Check trading results
        tr = results["trading_results"]
        assert tr["initial_capital"] == 197.0
        assert tr["final_capital"] >= tr["initial_capital"]
        assert tr["total_profit"] >= 0
        assert tr["winning_trades"] + tr["losing_trades"] == tr["trades_executed"]

    def test_backtest_with_different_capital_amounts(self):
        """Test backtest with different capital allocations."""
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=50,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=50,
            days=30,
        )
        
        engine = BacktestEngine()
        
        # Test with small capital per trade
        results_small = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=10.0,
        )
        
        # Test with large capital per trade
        results_large = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=100.0,
        )
        
        # Larger capital per trade should result in higher final capital
        assert results_large["trading_results"]["final_capital"] >= \
               results_small["trading_results"]["final_capital"]

    def test_backtest_profitability(self):
        """Test that backtest shows profitability metrics."""
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=100,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=100,
            days=30,
        )
        
        engine = BacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        tr = results["trading_results"]
        
        # Should show positive ROI
        assert tr["roi_percentage"] >= 0
        
        # Win rate should be between 0 and 100
        assert 0 <= tr["win_rate"] <= 100

    def test_backtest_data_point_accuracy(self):
        """Test backtest data point accuracy."""
        num_markets = 75
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=num_markets,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=75,
            days=30,
        )
        
        engine = BacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        dp = results["data_points"]
        assert dp["markets_analyzed"] == num_markets


class TestBacktestReporter:
    """Tests for backtest reporting."""

    def test_generate_report_basic(self):
        """Test report generation."""
        results = {
            "backtest_period": {
                "start": "2026-01-01",
                "end": "2026-01-31",
                "num_days": 31,
            },
            "data_points": {
                "markets_analyzed": 100,
                "opportunities_identified": 50,
                "buy_signals": 30,
            },
            "trading_results": {
                "trades_executed": 30,
                "initial_capital": 197.0,
                "final_capital": 5000.0,
                "total_profit": 4803.0,
                "roi_percentage": 2438.07,
                "winning_trades": 28,
                "losing_trades": 2,
                "win_rate": 93.3,
            },
            "strategy_parameters": {
                "min_liquidity": 50.0,
                "min_edge": 0.15,
                "max_price": 0.10,
                "min_confidence": 0.60,
            },
        }
        
        report = BacktestReporter.generate_report(results)
        
        assert "POLYMARKET BACKTEST REPORT" in report
        assert "BACKTEST PERIOD" in report
        assert "DATA ANALYSIS" in report
        assert "TRADING RESULTS" in report
        assert "STRATEGY PARAMETERS" in report
        assert "2026-01-01" in report
        assert "197.00" in report
        assert "5000.00" in report

    def test_report_contains_key_metrics(self):
        """Test report contains all key metrics."""
        results = {
            "backtest_period": {
                "start": "2026-01-01",
                "end": "2026-01-31",
                "num_days": 31,
            },
            "data_points": {
                "markets_analyzed": 100,
                "opportunities_identified": 50,
                "buy_signals": 30,
            },
            "trading_results": {
                "trades_executed": 30,
                "initial_capital": 197.0,
                "final_capital": 5000.0,
                "total_profit": 4803.0,
                "roi_percentage": 2438.07,
                "winning_trades": 28,
                "losing_trades": 2,
                "win_rate": 93.3,
            },
            "strategy_parameters": {
                "min_liquidity": 50.0,
                "min_edge": 0.15,
                "max_price": 0.10,
                "min_confidence": 0.60,
            },
        }
        
        report = BacktestReporter.generate_report(results)
        
        # Check for key metrics
        assert "Markets Analyzed:" in report
        assert "Trades Executed:" in report
        assert "Final Capital:" in report
        assert "Total ROI:" in report
        assert "Win Rate:" in report


class TestBacktestIntegration:
    """Integration tests for complete backtest workflow."""

    def test_end_to_end_backtest(self):
        """Test complete backtest workflow."""
        # Generate data
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=100,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=100,
            days=30,
        )
        
        # Run backtest
        engine = BacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Generate report
        report = BacktestReporter.generate_report(results)
        
        # Verify complete workflow
        assert results["trading_results"]["initial_capital"] == 197.0
        assert "POLYMARKET BACKTEST REPORT" in report
        assert len(report) > 100  # Report should have substantial content

    def test_backtest_scalability(self):
        """Test backtest with larger datasets."""
        # Generate larger dataset
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=500,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=500,
            days=30,
        )
        
        engine = BacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=25.0,
        )
        
        # Should handle large datasets
        assert results["data_points"]["markets_analyzed"] == 500
        assert results["trading_results"]["trades_executed"] > 0

    def test_backtest_consistency(self):
        """Test backtest produces consistent results."""
        markets = BacktestDataGenerator.generate_market_data(
            num_markets=100,
            days=30,
        )
        weather = BacktestDataGenerator.generate_weather_data(
            num_points=100,
            days=30,
        )
        
        engine = BacktestEngine()
        
        # Run backtest twice with same data
        results1 = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        results2 = engine.run_backtest(
            market_data=markets,
            weather_data=weather,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Results should be identical
        assert results1["trading_results"]["final_capital"] == \
               results2["trading_results"]["final_capital"]
        assert results1["trading_results"]["roi_percentage"] == \
               results2["trading_results"]["roi_percentage"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
