import os
import sys
import pytest
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

# Add project root to sys.path
root_path = Path(__file__).parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.polymarket_search_tool import WeatherSearchTool
from tests.test_utils import save_test_result

console = Console()

class TestWeatherSearch:
    """Pytest compatible test class."""
    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("POLYMARKET_API_KEY"), reason="POLYMARKET_API_KEY not set")
    async def test_weather_keyword_search(self):
        """Test searching with weather keywords and CLOB enrichment."""
        client = PolymarketClient(api_key=os.getenv("POLYMARKET_API_KEY"))
        search_tool = WeatherSearchTool(client)
        markets = await search_tool.search()
        assert len(markets) > 0
        await client.close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("POLYMARKET_API_KEY"), reason="POLYMARKET_API_KEY not set")
    async def test_city_weather_search(self):
        """Test searching for weather in a specific city."""
        client = PolymarketClient(api_key=os.getenv("POLYMARKET_API_KEY"))
        search_tool = WeatherSearchTool(client)
        city = "London"
        markets = await search_tool.search(city=city)
        if markets:
            for m in markets:
                assert city.lower() in m["question"].lower()
        await client.close()

async def run_standalone_search(city: str, query: str = "temperature"):
    """Run search and output to console + JSON."""
    if not os.getenv("POLYMARKET_API_KEY"):
        console.print("[bold red]Error: POLYMARKET_API_KEY not found in environment.[/bold red]")
        return

    client = PolymarketClient(api_key=os.getenv("POLYMARKET_API_KEY"))
    search_tool = WeatherSearchTool(client)
    
    console.print(f"[bold cyan]Searching Polymarket Weather for:[/bold cyan] [yellow]{city}[/yellow] (query: {query})")
    
    markets = await search_tool.search(query=query, city=city)
    
    if not markets:
        console.print(f"[bold red]No weather markets found for {city} right now.[/bold red]")
    else:
        # Create Table for console output
        table = Table(title=f"Weather Markets: {city}", show_header=True, header_style="bold magenta")
        table.add_column("Question", style="dim", width=60)
        table.add_column("Liquidity", justify="right")
        table.add_column("Yes Price", justify="right")
        table.add_column("Best Bid", justify="right", style="green")
        table.add_column("Best Ask", justify="right", style="red")

        for m in markets:
            clob = m.get("clob_details") or {}
            table.add_row(
                m["question"],
                f"${m['liquidity']:,.2f}",
                f"${m['yes_price']:.3f}",
                f"${clob.get('best_bid', 0):.3f}" if clob.get('best_bid') else "N/A",
                f"${clob.get('best_ask', 0):.3f}" if clob.get('best_ask') else "N/A"
            )
        
        console.print(table)
        
        # Save to JSON
        save_test_result(f"weather_search_{city.lower().replace(' ', '_')}", markets)
    
    await client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search Polymarket Weather Markets")
    parser.add_argument("city", nargs="?", default="London", help="City to search for (default: London)")
    parser.add_argument("--query", default="temperature", help="Keywords to search for")
    
    args = parser.parse_args()
    
    asyncio.run(run_standalone_search(args.city, args.query))
