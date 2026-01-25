"""Polymarket backtesting utility with historical data simulation."""
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

from agent.tools.polymarket_tool import PolymarketMarket
from agent.tools.weather_tool import WeatherForecast
from agent.tools.trading_strategy import (
    TradingStrategy,
    TradeOpportunity,
    PortfolioSimulator,
    TradeSignal,
)

logger = logging.getLogger(__name__)


@dataclass
class HistoricalMarketData:
    """Historical market data point."""
    timestamp: str
    market_id: str
    city: str
    question: str
    yes_price: float
    no_price: float
    liquidity: float
    volume: float
    actual_outcome: Optional[bool] = None  # True if YES won, False if NO won


@dataclass
class HistoricalWeatherData:
    """Historical weather data point."""
    timestamp: str
    city: str
    high_temp: float
    low_temp: float
    avg_temp: float
    condition: str
    actual_high: Optional[float] = None
    actual_low: Optional[float] = None


class BacktestDataGenerator:
    """Generate realistic historical data for backtesting."""

    @staticmethod
    def generate_market_data(
        num_markets: int = 100,
        days: int = 30,
    ) -> List[HistoricalMarketData]:
        """Generate synthetic historical market data.
        
        Args:
            num_markets: Number of market data points to generate
            days: Number of days to span
            
        Returns:
            List of historical market data
        """
        cities = ["London", "New York", "Seoul"]
        markets = []
        
        base_date = datetime.now() - timedelta(days=days)
        
        for i in range(num_markets):
            city = cities[i % len(cities)]
            timestamp = base_date + timedelta(hours=i * (days * 24 / num_markets))
            
            # Generate realistic market data
            yes_price = 0.03 + (i % 100) * 0.0007  # Range 0.03 to 0.10
            liquidity = 50 + (i % 200) * 2  # Range 50 to 450
            volume = liquidity * (2 + (i % 5))
            
            # Simulate actual outcome (random for now)
            actual_outcome = (i % 3) == 0  # 33% win rate
            
            market = HistoricalMarketData(
                timestamp=timestamp.isoformat(),
                market_id=f"market_{i}",
                city=city,
                question=f"Will {city} high temperature exceed 75°F?",
                yes_price=yes_price,
                no_price=1 - yes_price,
                liquidity=liquidity,
                volume=volume,
                actual_outcome=actual_outcome,
            )
            markets.append(market)
        
        return markets

    @staticmethod
    def generate_weather_data(
        num_points: int = 100,
        days: int = 30,
    ) -> List[HistoricalWeatherData]:
        """Generate synthetic historical weather data.
        
        Args:
            num_points: Number of data points to generate
            days: Number of days to span
            
        Returns:
            List of historical weather data
        """
        cities = ["London", "New York", "Seoul"]
        weather_data = []
        
        base_date = datetime.now() - timedelta(days=days)
        
        for i in range(num_points):
            city = cities[i % len(cities)]
            timestamp = base_date + timedelta(hours=i * (days * 24 / num_points))
            
            # Generate realistic temperature data
            if city == "London":
                base_high = 55 + (i % 20)
                base_low = 45 + (i % 15)
            elif city == "New York":
                base_high = 60 + (i % 25)
                base_low = 50 + (i % 20)
            else:  # Seoul
                base_high = 50 + (i % 30)
                base_low = 40 + (i % 25)
            
            high_temp = base_high + (i % 5) - 2
            low_temp = base_low + (i % 5) - 2
            avg_temp = (high_temp + low_temp) / 2
            
            weather = HistoricalWeatherData(
                timestamp=timestamp.isoformat(),
                city=city,
                high_temp=high_temp,
                low_temp=low_temp,
                avg_temp=avg_temp,
                condition="Partly Cloudy",
                actual_high=high_temp + (i % 3) - 1,
                actual_low=low_temp + (i % 3) - 1,
            )
            weather_data.append(weather)
        
        return weather_data


class BacktestEngine:
    """Engine for running backtests on historical data."""

    def __init__(self, strategy: Optional[TradingStrategy] = None):
        """Initialize backtest engine.
        
        Args:
            strategy: Trading strategy to backtest (uses defaults if None)
        """
        self.strategy = strategy or TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        self.results: List[Dict[str, Any]] = []

    def run_backtest(
        self,
        market_data: List[HistoricalMarketData],
        weather_data: List[HistoricalWeatherData],
        initial_capital: float = 197.0,
        capital_per_trade: float = 50.0,
    ) -> Dict[str, Any]:
        """Run backtest on historical data.
        
        Args:
            market_data: Historical market data
            weather_data: Historical weather data
            initial_capital: Starting capital
            capital_per_trade: Capital to allocate per trade
            
        Returns:
            Backtest results dictionary
        """
        simulator = PortfolioSimulator(initial_capital=initial_capital)
        
        # Create weather lookup
        weather_lookup = self._create_weather_lookup(weather_data)
        
        # Analyze each market
        opportunities = []
        for market in market_data:
            # Get weather for this city
            weather = weather_lookup.get(market.city)
            if not weather:
                continue
            
            # Calculate fair price based on weather
            fair_price = self._calculate_fair_price(market.question, weather)
            
            # Analyze market
            opportunity = self.strategy.analyze_market(
                market_id=market.market_id,
                city=market.city,
                market_question=market.question,
                market_price=market.yes_price,
                fair_price=fair_price,
                liquidity=market.liquidity,
            )
            opportunities.append((opportunity, market))
        
        # Filter for BUY signals
        buy_opportunities = [
            (opp, market) for opp, market in opportunities
            if opp.signal == TradeSignal.BUY
        ]
        
        # Execute trades
        trades_executed = 0
        for opportunity, market in buy_opportunities:
            if simulator.current_capital < capital_per_trade:
                break
            
            # Simulate trade outcome based on actual market outcome
            if market.actual_outcome:
                # YES won - profitable trade
                profit = capital_per_trade * opportunity.edge_percentage
            else:
                # NO won - losing trade
                profit = -capital_per_trade * opportunity.edge_percentage
            
            # Execute trade
            result = simulator.execute_trade(opportunity, capital_per_trade)
            if result["success"]:
                trades_executed += 1
        
        # Generate results
        summary = simulator.get_summary()
        
        return {
            "backtest_period": {
                "start": market_data[0].timestamp if market_data else None,
                "end": market_data[-1].timestamp if market_data else None,
                "num_days": len(set(m.timestamp[:10] for m in market_data)),
            },
            "data_points": {
                "markets_analyzed": len(market_data),
                "opportunities_identified": len(opportunities),
                "buy_signals": len(buy_opportunities),
            },
            "trading_results": {
                "trades_executed": trades_executed,
                "initial_capital": summary["initial_capital"],
                "final_capital": summary["current_capital"],
                "total_profit": summary["total_profit"],
                "total_roi": summary["total_roi"],
                "roi_percentage": summary["roi_percentage"],
                "winning_trades": summary["winning_trades"],
                "losing_trades": summary["losing_trades"],
                "win_rate": (
                    summary["winning_trades"] / max(summary["num_trades"], 1) * 100
                    if summary["num_trades"] > 0
                    else 0
                ),
            },
            "strategy_parameters": {
                "min_liquidity": self.strategy.min_liquidity,
                "min_edge": self.strategy.min_edge,
                "max_price": self.strategy.max_price,
                "min_confidence": self.strategy.min_confidence,
            },
        }

    def _create_weather_lookup(
        self,
        weather_data: List[HistoricalWeatherData],
    ) -> Dict[str, HistoricalWeatherData]:
        """Create lookup of latest weather data by city.
        
        Args:
            weather_data: Historical weather data
            
        Returns:
            Dictionary mapping city to latest weather
        """
        lookup = {}
        for weather in weather_data:
            lookup[weather.city] = weather
        return lookup

    def _calculate_fair_price(
        self,
        question: str,
        weather: HistoricalWeatherData,
    ) -> float:
        """Calculate fair price based on weather data.
        
        Args:
            question: Market question
            weather: Weather data
            
        Returns:
            Fair price probability
        """
        # Simple heuristic: if actual high > 75, fair price is high
        if "high" in question.lower() and "exceed 75" in question.lower():
            if weather.actual_high and weather.actual_high > 75:
                return 0.75
            else:
                return 0.25
        elif "low" in question.lower() and "exceed 50" in question.lower():
            if weather.actual_low and weather.actual_low > 50:
                return 0.75
            else:
                return 0.25
        
        return 0.5


class BacktestReporter:
    """Generate backtest reports."""

    @staticmethod
    def generate_report(
        backtest_results: Dict[str, Any],
        output_file: Optional[str] = None,
    ) -> str:
        """Generate human-readable backtest report.
        
        Args:
            backtest_results: Results from backtest
            output_file: Optional file to save report
            
        Returns:
            Report as string
        """
        report = []
        report.append("=" * 60)
        report.append("POLYMARKET BACKTEST REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Backtest period
        bp = backtest_results.get("backtest_period", {})
        report.append("BACKTEST PERIOD")
        report.append("-" * 60)
        report.append(f"Start Date:     {bp.get('start', 'N/A')}")
        report.append(f"End Date:       {bp.get('end', 'N/A')}")
        report.append(f"Duration:       {bp.get('num_days', 'N/A')} days")
        report.append("")
        
        # Data points
        dp = backtest_results.get("data_points", {})
        report.append("DATA ANALYSIS")
        report.append("-" * 60)
        report.append(f"Markets Analyzed:       {dp.get('markets_analyzed', 0)}")
        report.append(f"Opportunities Found:    {dp.get('opportunities_identified', 0)}")
        report.append(f"BUY Signals Generated:  {dp.get('buy_signals', 0)}")
        report.append("")
        
        # Trading results
        tr = backtest_results.get("trading_results", {})
        report.append("TRADING RESULTS")
        report.append("-" * 60)
        report.append(f"Trades Executed:        {tr.get('trades_executed', 0)}")
        report.append(f"Initial Capital:        ${tr.get('initial_capital', 0):.2f}")
        report.append(f"Final Capital:          ${tr.get('final_capital', 0):.2f}")
        report.append(f"Total Profit:           ${tr.get('total_profit', 0):.2f}")
        report.append(f"Total ROI:              {tr.get('roi_percentage', 0):.2f}%")
        report.append(f"Winning Trades:         {tr.get('winning_trades', 0)}")
        report.append(f"Losing Trades:          {tr.get('losing_trades', 0)}")
        report.append(f"Win Rate:               {tr.get('win_rate', 0):.1f}%")
        report.append("")
        
        # Strategy parameters
        sp = backtest_results.get("strategy_parameters", {})
        report.append("STRATEGY PARAMETERS")
        report.append("-" * 60)
        report.append(f"Min Liquidity:          ${sp.get('min_liquidity', 0):.2f}")
        report.append(f"Min Edge:               {sp.get('min_edge', 0)*100:.1f}%")
        report.append(f"Max Price:              ${sp.get('max_price', 0):.4f}")
        report.append(f"Min Confidence:         {sp.get('min_confidence', 0):.1%}")
        report.append("")
        report.append("=" * 60)
        
        report_text = "\n".join(report)
        
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                f.write(report_text)
        
        return report_text


async def run_backtest_analysis(
    num_markets: int = 100,
    num_weather_points: int = 100,
    days: int = 30,
    initial_capital: float = 197.0,
    output_dir: str = "test-results",
) -> Dict[str, Any]:
    """Run complete backtest analysis.
    
    Args:
        num_markets: Number of market data points
        num_weather_points: Number of weather data points
        days: Number of days to simulate
        initial_capital: Starting capital
        output_dir: Directory to save results
        
    Returns:
        Backtest results
    """
    logger.info("Generating historical data...")
    
    # Generate data
    market_data = BacktestDataGenerator.generate_market_data(
        num_markets=num_markets,
        days=days,
    )
    weather_data = BacktestDataGenerator.generate_weather_data(
        num_points=num_weather_points,
        days=days,
    )
    
    logger.info(f"Generated {len(market_data)} market data points")
    logger.info(f"Generated {len(weather_data)} weather data points")
    
    # Run backtest
    logger.info("Running backtest...")
    engine = BacktestEngine()
    results = engine.run_backtest(
        market_data=market_data,
        weather_data=weather_data,
        initial_capital=initial_capital,
    )
    
    # Generate report
    logger.info("Generating report...")
    report = BacktestReporter.generate_report(results)
    print(report)
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save JSON results
    results_file = output_path / f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {results_file}")
    
    # Save report
    report_file = output_path / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w") as f:
        f.write(report)
    logger.info(f"Report saved to {report_file}")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_backtest_analysis())
