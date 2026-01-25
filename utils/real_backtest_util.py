"""Real backtesting utility using actual API data."""
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

from agent.tools.trading_strategy import (
    TradingStrategy,
    PortfolioSimulator,
    TradeSignal,
)
from utils.real_historical_data import (
    RealHistoricalDataFetcher,
    RealHistoricalMarketData,
    RealHistoricalWeatherData,
)

logger = logging.getLogger(__name__)


class RealBacktestEngine:
    """Backtest engine using real API data."""

    def __init__(self, strategy: Optional[TradingStrategy] = None):
        """Initialize backtest engine.
        
        Args:
            strategy: Trading strategy (uses defaults if None)
        """
        self.strategy = strategy or TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )

    def run_backtest(
        self,
        market_data: List[RealHistoricalMarketData],
        weather_data: Dict[str, List[RealHistoricalWeatherData]],
        initial_capital: float = 197.0,
        capital_per_trade: float = 50.0,
    ) -> Dict[str, Any]:
        """Run backtest on real market data.
        
        Args:
            market_data: Real market data from Polymarket
            weather_data: Real weather data from Tomorrow.io
            initial_capital: Starting capital
            capital_per_trade: Capital per trade
            
        Returns:
            Backtest results
        """
        simulator = PortfolioSimulator(initial_capital=initial_capital)
        
        # Create weather lookup
        weather_lookup = self._create_weather_lookup(weather_data)
        
        # Analyze each market
        opportunities = []
        for market in market_data:
            # Get weather for this city
            weather = weather_lookup.get(market.city)
            if not weather or not weather:
                continue
            
            # Use most recent weather data
            latest_weather = weather[-1] if weather else None
            if not latest_weather:
                continue
            
            # Calculate fair price based on weather
            fair_price = self._calculate_fair_price(market.question, latest_weather)
            
            # Analyze market
            opportunity = self.strategy.analyze_market(
                market_id=market.market_id,
                city=market.city,
                market_question=market.question,
                market_price=market.yes_price,
                fair_price=fair_price,
                liquidity=market.liquidity,
            )
            opportunities.append(opportunity)
        
        # Filter for BUY signals
        buy_opportunities = [
            opp for opp in opportunities
            if opp.signal == TradeSignal.BUY
        ]
        
        # Execute trades
        trades_executed = 0
        for opportunity in buy_opportunities:
            if simulator.current_capital < capital_per_trade:
                break
            
            result = simulator.execute_trade(opportunity, capital_per_trade)
            if result["success"]:
                trades_executed += 1
        
        # Generate results
        summary = simulator.get_summary()
        
        return {
            "backtest_info": {
                "timestamp": datetime.now().isoformat(),
                "data_source": "Real API Data (Polymarket + Tomorrow.io)",
                "markets_analyzed": len(market_data),
                "cities_covered": list(weather_lookup.keys()),
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
            "market_sample": [
                {
                    "city": m.city,
                    "question": m.question,
                    "yes_price": m.yes_price,
                    "liquidity": m.liquidity,
                }
                for m in market_data[:5]
            ],
        }

    def _create_weather_lookup(
        self,
        weather_data: Dict[str, List[RealHistoricalWeatherData]],
    ) -> Dict[str, List[RealHistoricalWeatherData]]:
        """Create lookup of weather data by city.
        
        Args:
            weather_data: Weather data by city
            
        Returns:
            Dictionary mapping city to weather list
        """
        return weather_data

    def _calculate_fair_price(
        self,
        question: str,
        weather: RealHistoricalWeatherData,
    ) -> float:
        """Calculate fair price based on real weather data.
        
        Args:
            question: Market question
            weather: Weather data
            
        Returns:
            Fair price probability
        """
        # Analyze question for temperature thresholds
        question_lower = question.lower()
        
        # Extract threshold temperature if mentioned
        threshold = 75  # Default
        
        # Look for common patterns
        if "exceed" in question_lower or "above" in question_lower:
            # Try to extract number
            import re
            numbers = re.findall(r'\d+', question_lower)
            if numbers:
                threshold = int(numbers[0])
        
        # Calculate probability based on weather
        if "high" in question_lower:
            if weather.high_temp > threshold:
                return 0.75
            else:
                return 0.25
        elif "low" in question_lower:
            if weather.low_temp > threshold:
                return 0.75
            else:
                return 0.25
        
        # Default: use average temperature
        if weather.avg_temp > threshold:
            return 0.65
        else:
            return 0.35


class RealBacktestReporter:
    """Generate reports from real backtest results."""

    @staticmethod
    def generate_report(results: Dict[str, Any]) -> str:
        """Generate human-readable report.
        
        Args:
            results: Backtest results
            
        Returns:
            Report string
        """
        report = []
        report.append("=" * 70)
        report.append("POLYMARKET REAL DATA BACKTEST REPORT")
        report.append("=" * 70)
        report.append("")
        
        # Backtest info
        info = results.get("backtest_info", {})
        report.append("BACKTEST INFORMATION")
        report.append("-" * 70)
        report.append(f"Timestamp:              {info.get('timestamp', 'N/A')}")
        report.append(f"Data Source:            {info.get('data_source', 'N/A')}")
        report.append(f"Markets Analyzed:       {info.get('markets_analyzed', 0)}")
        report.append(f"Cities Covered:         {', '.join(info.get('cities_covered', []))}")
        report.append("")
        
        # Data points
        dp = results.get("data_points", {})
        report.append("DATA ANALYSIS")
        report.append("-" * 70)
        report.append(f"Markets Analyzed:       {dp.get('markets_analyzed', 0)}")
        report.append(f"Opportunities Found:    {dp.get('opportunities_identified', 0)}")
        report.append(f"BUY Signals Generated:  {dp.get('buy_signals', 0)}")
        report.append("")
        
        # Trading results
        tr = results.get("trading_results", {})
        report.append("TRADING RESULTS")
        report.append("-" * 70)
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
        sp = results.get("strategy_parameters", {})
        report.append("STRATEGY PARAMETERS")
        report.append("-" * 70)
        report.append(f"Min Liquidity:          ${sp.get('min_liquidity', 0):.2f}")
        report.append(f"Min Edge:               {sp.get('min_edge', 0)*100:.1f}%")
        report.append(f"Max Price:              ${sp.get('max_price', 0):.4f}")
        report.append(f"Min Confidence:         {sp.get('min_confidence', 0):.1%}")
        report.append("")
        
        # Market sample
        sample = results.get("market_sample", [])
        if sample:
            report.append("SAMPLE MARKETS ANALYZED")
            report.append("-" * 70)
            for i, market in enumerate(sample, 1):
                report.append(f"{i}. {market['city']}: {market['question'][:50]}...")
                report.append(f"   Price: ${market['yes_price']:.4f}, Liquidity: ${market['liquidity']:.2f}")
            report.append("")
        
        report.append("=" * 70)
        
        return "\n".join(report)


async def run_real_backtest(
    tomorrow_io_key: str,
    polymarket_api_key: Optional[str] = None,
    output_dir: str = "test-results",
) -> Dict[str, Any]:
    """Run complete real backtest with API data.
    
    Args:
        tomorrow_io_key: Tomorrow.io API key
        polymarket_api_key: Optional Polymarket API key
        output_dir: Directory to save results
        
    Returns:
        Backtest results
    """
    logger.info("Starting real backtest with API data...")
    
    # Fetch real data
    fetcher = RealHistoricalDataFetcher(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=polymarket_api_key,
    )
    
    try:
        # Fetch Polymarket data
        logger.info("Fetching Polymarket weather markets...")
        markets = await fetcher.fetch_polymarket_weather_markets(
            search_query="weather",
            limit=100,
        )
        
        if not markets:
            logger.warning("No markets found")
            return {}
        
        # Fetch Tomorrow.io data
        logger.info("Fetching Tomorrow.io weather data...")
        weather_data = await fetcher.fetch_all_cities_weather(
            cities=["London", "New York", "Seoul"],
        )
        
        # Run backtest
        logger.info("Running backtest on real data...")
        engine = RealBacktestEngine()
        results = engine.run_backtest(
            market_data=markets,
            weather_data=weather_data,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Generate report
        report = RealBacktestReporter.generate_report(results)
        print("\n" + report)
        
        # Save results
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        results_file = output_path / f"real_backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {results_file}")
        
        # Save report
        report_file = output_path / f"real_backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {report_file}")
        
        return results
    
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
    
    asyncio.run(run_real_backtest(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=polymarket_key,
    ))
