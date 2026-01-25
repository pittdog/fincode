"""Real backtesting with detailed trade execution tracking."""
import json
import csv
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging
from dataclasses import dataclass, asdict, field

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


@dataclass
class TradeExecution:
    """Detailed trade execution record."""
    trade_id: str
    timestamp_placed: str
    market_id: str
    city: str
    market_question: str
    signal: str
    entry_price: float
    position_size: float
    capital_allocated: float
    fair_price: float
    edge_percentage: float
    
    # Resolution fields
    timestamp_resolved: Optional[str] = None
    resolution_price: Optional[float] = None
    outcome: Optional[str] = None  # WIN, LOSS, PENDING
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class TradeTracker:
    """Track individual trade executions."""
    
    def __init__(self):
        """Initialize trade tracker."""
        self.trades: List[TradeExecution] = []
        self.trade_counter = 0
    
    def record_trade(
        self,
        market_id: str,
        city: str,
        market_question: str,
        signal: str,
        entry_price: float,
        position_size: float,
        capital_allocated: float,
        fair_price: float,
        edge_percentage: float,
    ) -> TradeExecution:
        """Record a new trade execution.
        
        Args:
            market_id: Market identifier
            city: City name
            market_question: Market question text
            signal: Trading signal (BUY, SELL, etc.)
            entry_price: Entry price
            position_size: Position size
            capital_allocated: Capital allocated to trade
            fair_price: Fair price calculated
            edge_percentage: Edge percentage
            
        Returns:
            TradeExecution record
        """
        self.trade_counter += 1
        trade = TradeExecution(
            trade_id=f"TRADE_{self.trade_counter:04d}",
            timestamp_placed=datetime.now().isoformat(),
            market_id=market_id,
            city=city,
            market_question=market_question,
            signal=signal,
            entry_price=entry_price,
            position_size=position_size,
            capital_allocated=capital_allocated,
            fair_price=fair_price,
            edge_percentage=edge_percentage,
        )
        self.trades.append(trade)
        return trade
    
    def resolve_trade(
        self,
        trade_id: str,
        resolution_price: float,
        outcome: str,
        exit_price: float,
    ) -> Optional[TradeExecution]:
        """Resolve a trade with outcome.
        
        Args:
            trade_id: Trade identifier
            resolution_price: Market resolution price
            outcome: WIN or LOSS
            exit_price: Exit price
            
        Returns:
            Updated TradeExecution or None
        """
        for trade in self.trades:
            if trade.trade_id == trade_id:
                trade.timestamp_resolved = datetime.now().isoformat()
                trade.resolution_price = resolution_price
                trade.outcome = outcome
                trade.exit_price = exit_price
                
                # Calculate PnL
                if outcome == "WIN":
                    pnl = trade.capital_allocated * trade.edge_percentage
                else:
                    pnl = -trade.capital_allocated * trade.edge_percentage
                
                trade.pnl = pnl
                trade.pnl_percentage = (pnl / trade.capital_allocated * 100) if trade.capital_allocated > 0 else 0
                
                return trade
        
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get trade summary statistics.
        
        Returns:
            Summary dictionary
        """
        total_trades = len(self.trades)
        resolved_trades = [t for t in self.trades if t.outcome]
        winning_trades = [t for t in resolved_trades if t.outcome == "WIN"]
        losing_trades = [t for t in resolved_trades if t.outcome == "LOSS"]
        
        total_pnl = sum(t.pnl for t in resolved_trades if t.pnl is not None)
        total_capital = sum(t.capital_allocated for t in self.trades)
        
        return {
            "total_trades": total_trades,
            "resolved_trades": len(resolved_trades),
            "pending_trades": total_trades - len(resolved_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (len(winning_trades) / len(resolved_trades) * 100) if resolved_trades else 0,
            "total_pnl": total_pnl,
            "total_capital": total_capital,
            "roi_percentage": (total_pnl / total_capital * 100) if total_capital > 0 else 0,
        }


class EnhancedRealBacktestEngine:
    """Enhanced backtest engine with detailed trade tracking."""

    def __init__(self, strategy: Optional[TradingStrategy] = None):
        """Initialize backtest engine.
        
        Args:
            strategy: Trading strategy
        """
        self.strategy = strategy or TradingStrategy(
            min_liquidity=50.0,
            min_edge=0.15,
            max_price=0.10,
            min_confidence=0.60,
        )
        self.trade_tracker = TradeTracker()

    def run_backtest_with_trades(
        self,
        market_data: List[RealHistoricalMarketData],
        weather_data: Dict[str, List[RealHistoricalWeatherData]],
        initial_capital: float = 197.0,
        capital_per_trade: float = 50.0,
    ) -> Dict[str, Any]:
        """Run backtest with detailed trade tracking.
        
        Args:
            market_data: Real market data
            weather_data: Real weather data
            initial_capital: Starting capital
            capital_per_trade: Capital per trade
            
        Returns:
            Backtest results with trade details
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
            
            # Calculate fair price
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
            opportunities.append((opportunity, market, fair_price))
        
        # Filter for BUY signals
        buy_opportunities = [
            (opp, market, fair_price) for opp, market, fair_price in opportunities
            if opp.signal == TradeSignal.BUY
        ]
        
        logger.info(f"Found {len(buy_opportunities)} BUY opportunities")
        
        # Execute trades with tracking
        for opportunity, market, fair_price in buy_opportunities:
            if simulator.current_capital < capital_per_trade:
                logger.info("Insufficient capital for more trades")
                break
            
            # Record trade execution
            trade = self.trade_tracker.record_trade(
                market_id=market.market_id,
                city=market.city,
                market_question=market.question,
                signal=opportunity.signal.name,
                entry_price=market.yes_price,
                position_size=capital_per_trade / market.yes_price,
                capital_allocated=capital_per_trade,
                fair_price=fair_price,
                edge_percentage=opportunity.edge_percentage,
            )
            
            # Execute trade in simulator
            result = simulator.execute_trade(opportunity, capital_per_trade)
            
            if result["success"]:
                # Simulate trade resolution
                # In real scenario, this would be resolved when market closes
                outcome = "WIN" if (fair_price > market.yes_price) else "LOSS"
                resolution_price = fair_price
                exit_price = resolution_price if outcome == "WIN" else market.yes_price
                
                # Resolve trade
                self.trade_tracker.resolve_trade(
                    trade_id=trade.trade_id,
                    resolution_price=resolution_price,
                    outcome=outcome,
                    exit_price=exit_price,
                )
                
                logger.info(f"Trade {trade.trade_id}: {outcome} - PnL: ${trade.pnl:.2f}")
        
        # Get summary
        summary = simulator.get_summary()
        trade_summary = self.trade_tracker.get_summary()
        
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
                "trades_executed": trade_summary["total_trades"],
                "initial_capital": summary["initial_capital"],
                "final_capital": summary["current_capital"],
                "total_profit": summary["total_profit"],
                "total_roi": summary["total_roi"],
                "roi_percentage": summary["roi_percentage"],
                "winning_trades": trade_summary["winning_trades"],
                "losing_trades": trade_summary["losing_trades"],
                "win_rate": trade_summary["win_rate"],
            },
            "strategy_parameters": {
                "min_liquidity": self.strategy.min_liquidity,
                "min_edge": self.strategy.min_edge,
                "max_price": self.strategy.max_price,
                "min_confidence": self.strategy.min_confidence,
            },
            "trades": [t.to_dict() for t in self.trade_tracker.trades],
            "trade_summary": trade_summary,
        }

    def _create_weather_lookup(
        self,
        weather_data: Dict[str, List[RealHistoricalWeatherData]],
    ) -> Dict[str, List[RealHistoricalWeatherData]]:
        """Create lookup of weather data by city."""
        return weather_data

    def _calculate_fair_price(
        self,
        question: str,
        weather: RealHistoricalWeatherData,
    ) -> float:
        """Calculate fair price based on weather."""
        question_lower = question.lower()
        
        threshold = 75
        
        if "exceed" in question_lower or "above" in question_lower:
            import re
            numbers = re.findall(r'\d+', question_lower)
            if numbers:
                threshold = int(numbers[0])
        
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
        
        if weather.avg_temp > threshold:
            return 0.65
        else:
            return 0.35


def save_trades_to_csv(
    trades: List[Dict[str, Any]],
    output_file: str,
) -> None:
    """Save trade executions to CSV.
    
    Args:
        trades: List of trade dictionaries
        output_file: Output CSV file path
    """
    if not trades:
        logger.warning("No trades to save")
        return
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Define CSV columns
    fieldnames = [
        "trade_id",
        "timestamp_placed",
        "market_id",
        "city",
        "market_question",
        "signal",
        "entry_price",
        "position_size",
        "capital_allocated",
        "fair_price",
        "edge_percentage",
        "timestamp_resolved",
        "resolution_price",
        "outcome",
        "exit_price",
        "pnl",
        "pnl_percentage",
    ]
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for trade in trades:
            row = {field: trade.get(field, '') for field in fieldnames}
            writer.writerow(row)
    
    logger.info(f"Saved {len(trades)} trades to {output_file}")


async def run_real_backtest_with_trades(
    tomorrow_io_key: str,
    polymarket_api_key: Optional[str] = None,
    output_dir: str = "test-results",
) -> Dict[str, Any]:
    """Run real backtest with detailed trade tracking.
    
    Args:
        tomorrow_io_key: Tomorrow.io API key
        polymarket_api_key: Optional Polymarket API key
        output_dir: Output directory
        
    Returns:
        Backtest results
    """
    logger.info("Starting real backtest with trade tracking...")
    
    fetcher = RealHistoricalDataFetcher(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=polymarket_api_key,
    )
    
    try:
        # Fetch data
        logger.info("Fetching Polymarket weather markets...")
        markets = await fetcher.fetch_polymarket_weather_markets(
            search_query="weather",
            limit=100,
        )
        
        if not markets:
            logger.warning("No markets found")
            return {}
        
        logger.info(f"Fetching Tomorrow.io weather data for {len(['London', 'New York', 'Seoul'])} cities...")
        weather_data = await fetcher.fetch_all_cities_weather(
            cities=["London", "New York", "Seoul"],
        )
        
        # Run backtest
        logger.info("Running backtest with trade tracking...")
        engine = EnhancedRealBacktestEngine()
        results = engine.run_backtest_with_trades(
            market_data=markets,
            weather_data=weather_data,
            initial_capital=197.0,
            capital_per_trade=50.0,
        )
        
        # Save results
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = output_path / f"real_backtest_results_{timestamp}.json"
        with open(results_file, "w") as f:
            # Remove trades from JSON for cleaner output
            json_results = {k: v for k, v in results.items() if k != "trades"}
            json.dump(json_results, f, indent=2)
        logger.info(f"Results saved to {results_file}")
        
        # Save trades to CSV
        csv_file = output_path / f"real_backtest_trades_{timestamp}.csv"
        save_trades_to_csv(results.get("trades", []), str(csv_file))
        
        # Print summary
        print("\n" + "=" * 70)
        print("TRADE EXECUTION SUMMARY")
        print("=" * 70)
        trade_summary = results.get("trade_summary", {})
        print(f"Total Trades Executed:    {trade_summary.get('total_trades', 0)}")
        print(f"Winning Trades:           {trade_summary.get('winning_trades', 0)}")
        print(f"Losing Trades:            {trade_summary.get('losing_trades', 0)}")
        print(f"Win Rate:                 {trade_summary.get('win_rate', 0):.1f}%")
        print(f"Total PnL:                ${trade_summary.get('total_pnl', 0):.2f}")
        print(f"ROI:                      {trade_summary.get('roi_percentage', 0):.2f}%")
        print("=" * 70 + "\n")
        
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
    
    asyncio.run(run_real_backtest_with_trades(
        tomorrow_io_key=tomorrow_io_key,
        polymarket_api_key=polymarket_key,
    ))
