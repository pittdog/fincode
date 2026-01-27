#!/usr/bin/env python3
"""Polymarket weather trading agent CLI entry point."""
import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.weather_tool import WeatherClient
from agent.tools.trading_strategy import (
    TradingStrategy,
    PortfolioSimulator,
    TradeSignal,
)


class PolyAgentCLI:
    """CLI for Polymarket weather trading agent."""

    def __init__(self):
        """Initialize the CLI."""
        self.console = Console()
        self.polymarket_client: Optional[PolymarketClient] = None
        self.weather_client: Optional[WeatherClient] = None
        self.strategy: Optional[TradingStrategy] = None
        self.simulator: Optional[PortfolioSimulator] = None
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from environment."""
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        return {
            "polymarket_api_key": os.getenv("POLYMARKET_API_KEY"),
            "weather_api_key": os.getenv("TOMORROWIO_API_KEY"),
            "min_liquidity": float(os.getenv("MIN_LIQUIDITY", "50.0")),
            "min_edge": float(os.getenv("MIN_EDGE", "0.15")),
            "max_price": float(os.getenv("MAX_PRICE", "0.10")),
            "min_confidence": float(os.getenv("MIN_CONFIDENCE", "0.60")),
            "initial_capital": float(os.getenv("INITIAL_CAPITAL", "197.0")),
            "cities": os.getenv("CITIES", "London,New York,Seoul").split(","),
        }

    async def initialize(self):
        """Initialize clients and strategy."""
        self.console.print("[bold cyan]Initializing Polymarket Trading Agent...[/bold cyan]")

        # Check required API keys
        if not self.config["weather_api_key"]:
            self.console.print("[red]Error: TOMORROWIO_API_KEY not set[/red]")
            return False

        try:
            self.polymarket_client = PolymarketClient(
                api_key=self.config["polymarket_api_key"]
            )
            self.weather_client = WeatherClient(
                api_key=self.config["weather_api_key"]
            )
            self.strategy = TradingStrategy(
                min_liquidity=self.config["min_liquidity"],
                min_edge=self.config["min_edge"],
                max_price=self.config["max_price"],
                min_confidence=self.config["min_confidence"],
            )
            self.simulator = PortfolioSimulator(
                initial_capital=self.config["initial_capital"]
            )

            self.console.print("[green]✓ Initialization complete[/green]")
            return True
        except Exception as e:
            self.console.print(f"[red]Error during initialization: {e}[/red]")
            return False

    async def scan_weather_markets(self) -> List[dict]:
        """Scan Polymarket for weather markets."""
        if not self.polymarket_client:
            self.console.print("[red]Client not initialized[/red]")
            return []

        self.console.print("\n[bold yellow]Scanning weather markets...[/bold yellow]")

        try:
            markets = await self.polymarket_client.search_weather_markets(
                cities=self.config["cities"],
                min_liquidity=self.config["min_liquidity"],
                max_price=self.config["max_price"],
            )

            self.console.print(f"[green]Found {len(markets)} matching markets[/green]")
            return markets
        except Exception as e:
            self.console.print(f"[red]Error scanning markets: {e}[/red]")
            return []

    async def fetch_weather_data(self) -> dict:
        """Fetch weather forecasts for configured cities."""
        if not self.weather_client:
            self.console.print("[red]Weather client not initialized[/red]")
            return {}

        self.console.print("\n[bold yellow]Fetching weather forecasts...[/bold yellow]")

        try:
            forecasts = await self.weather_client.get_forecasts_for_cities(
                cities=self.config["cities"]
            )

            self.console.print(f"[green]Fetched forecasts for {len(forecasts)} cities[/green]")
            return forecasts
        except Exception as e:
            self.console.print(f"[red]Error fetching weather: {e}[/red]")
            return {}

    async def analyze_opportunities(self, markets: List[dict], forecasts: dict) -> List[dict]:
        """Analyze markets for trading opportunities."""
        if not self.strategy:
            self.console.print("[red]Strategy not initialized[/red]")
            return []

        self.console.print("\n[bold yellow]Analyzing trading opportunities...[/bold yellow]")

        opportunities = []

        for market in markets:
            try:
                # Extract city from market question
                city = self._extract_city(market.question)
                if not city or city not in forecasts:
                    continue

                forecast = forecasts.get(city)
                if not forecast:
                    continue

                # Calculate fair price based on weather forecast
                fair_price = self._calculate_fair_price(forecast, market.question)

                # Analyze market
                opportunity = self.strategy.analyze_market(
                    market_id=market.id,
                    city=city,
                    market_question=market.question,
                    market_price=market.yes_price,
                    fair_price=fair_price,
                    liquidity=market.liquidity,
                )

                opportunities.append(opportunity)
            except Exception as e:
                self.console.print(f"[yellow]Warning: Error analyzing market {market.id}: {e}[/yellow]")
                continue

        # Rank opportunities
        ranked = self.strategy.rank_opportunities(opportunities)
        self.console.print(f"[green]Analyzed {len(ranked)} opportunities[/green]")

        return ranked

    def _extract_city(self, question: str) -> Optional[str]:
        """Extract city name from market question."""
        for city in self.config["cities"]:
            if city.lower() in question.lower():
                return city
        return None

    def _calculate_fair_price(self, forecast, question: str) -> float:
        """Calculate fair price based on weather forecast.
        
        This is a simplified calculation. In production, this would be more sophisticated.
        """
        # Extract temperature threshold from question
        # Example: "Will London's high temperature exceed 75°F?"
        
        # For now, use a simple heuristic based on forecast probabilities
        if "high" in question.lower():
            return forecast.probability_high
        elif "low" in question.lower():
            return forecast.probability_low
        else:
            return forecast.probability_avg

    def display_market_analysis(self, opportunities: List[dict]):
        """Display market analysis in a table."""
        if not opportunities:
            self.console.print("[yellow]No opportunities to display[/yellow]")
            return

        table = Table(title="Trading Opportunities Analysis")
        table.add_column("City", style="cyan")
        table.add_column("Signal", style="magenta")
        table.add_column("Market Price", justify="right")
        table.add_column("Fair Price", justify="right")
        table.add_column("Edge %", justify="right")
        table.add_column("Confidence", justify="right")
        table.add_column("Liquidity", justify="right")

        for opp in opportunities[:10]:  # Show top 10
            signal_style = {
                "BUY": "green",
                "SELL": "red",
                "HOLD": "yellow",
                "SKIP": "dim",
            }.get(opp.signal.value, "white")

            table.add_row(
                opp.city,
                f"[{signal_style}]{opp.signal.value}[/{signal_style}]",
                f"${opp.market_price:.4f}",
                f"${opp.fair_price:.4f}",
                f"{opp.edge_percentage*100:+.2f}%",
                f"{opp.confidence:.2%}",
                f"${opp.liquidity:.2f}",
            )

        self.console.print(table)

    async def simulate_trades(self, opportunities: List[dict]):
        """Simulate trading based on opportunities."""
        if not self.simulator:
            self.console.print("[red]Simulator not initialized[/red]")
            return

        self.console.print("\n[bold yellow]Simulating trades...[/bold yellow]")

        # Filter for BUY signals
        buy_opportunities = self.strategy.filter_opportunities(
            opportunities, TradeSignal.BUY
        )

        if not buy_opportunities:
            self.console.print("[yellow]No BUY signals found[/yellow]")
            return

        # Simulate trades with capital allocation
        capital_per_trade = self.simulator.current_capital / max(len(buy_opportunities), 1)

        with Progress() as progress:
            task = progress.add_task("[cyan]Executing trades...", total=len(buy_opportunities))

            for opp in buy_opportunities:
                result = self.simulator.execute_trade(opp, capital_per_trade)
                progress.update(task, advance=1)

                if result["success"]:
                    trade = result["trade"]
                    self.console.print(
                        f"[green]✓ Trade executed:[/green] {trade['city']} "
                        f"ROI: {trade['roi']*100:+.2f}% | "
                        f"Capital: ${result['capital']:.2f}"
                    )

    def display_portfolio_summary(self):
        """Display portfolio summary."""
        if not self.simulator:
            self.console.print("[red]Simulator not initialized[/red]")
            return

        summary = self.simulator.get_summary()

        panel_text = f"""
[bold]Portfolio Summary[/bold]

Initial Capital:     ${summary['initial_capital']:.2f}
Current Capital:     ${summary['current_capital']:.2f}
Total Profit:        ${summary['total_profit']:.2f}
Total ROI:           {summary['roi_percentage']:.2f}%

Trades Executed:     {summary['num_trades']}
Winning Trades:      {summary['winning_trades']}
Losing Trades:       {summary['losing_trades']}
Win Rate:            {summary['winning_trades']/max(summary['num_trades'], 1)*100:.1f}%
        """

        self.console.print(Panel(panel_text, title="Portfolio Performance"))

    async def run_full_analysis(self):
        """Run full market analysis and simulation."""
        # Initialize
        if not await self.initialize():
            return

        # Scan markets
        markets = await self.scan_weather_markets()
        if not markets:
            self.console.print("[yellow]No markets found[/yellow]")
            return

        # Fetch weather data
        forecasts = await self.fetch_weather_data()
        if not forecasts:
            self.console.print("[yellow]No weather data available[/yellow]")
            return

        # Analyze opportunities
        opportunities = await self.analyze_opportunities(markets, forecasts)

        # Display analysis
        self.display_market_analysis(opportunities)

        # Simulate trades
        await self.simulate_trades(opportunities)

        # Display summary
        self.display_portfolio_summary()

        # Save results
        await self.save_results(opportunities)

    async def save_results(self, opportunities: List[dict]):
        """Save analysis results to file."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "opportunities": [
                {
                    "market_id": opp.market_id,
                    "city": opp.city,
                    "signal": opp.signal.value,
                    "market_price": opp.market_price,
                    "fair_price": opp.fair_price,
                    "edge_percentage": opp.edge_percentage,
                    "confidence": opp.confidence,
                    "liquidity": opp.liquidity,
                    "reasoning": opp.reasoning,
                }
                for opp in opportunities
            ],
            "portfolio": self.simulator.get_summary() if self.simulator else {},
        }

        output_dir = Path(__file__).parent / "test-results"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"polyagent_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        self.console.print(f"\n[green]Results saved to {output_file}[/green]")

    async def cleanup(self):
        """Cleanup resources."""
        if self.polymarket_client:
            await self.polymarket_client.close()
        if self.weather_client:
            await self.weather_client.close()


async def main():
    """Main entry point."""
    cli = PolyAgentCLI()

    try:
        await cli.run_full_analysis()
    except KeyboardInterrupt:
        cli.console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        cli.console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        await cli.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
