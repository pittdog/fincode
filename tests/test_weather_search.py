import os
import sys
import pytest
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

# Add project root and tests directory to sys.path
root_path = Path(__file__).parent.parent
tests_path = Path(__file__).parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))
if str(tests_path) not in sys.path:
    sys.path.insert(0, str(tests_path))

from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.polymarket_search_tool import WeatherSearchTool
from test_utils import save_test_result

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
        # Filter markets to only show those with complete data (no N/As)
        complete_markets = [
            m for m in markets 
            if m.get("yes_book") and m.get("yes_book").get("best_bid") is not None
            and m.get("forecast_at_resolution")
        ]
        
        if not complete_markets:
            console.print(f"[bold yellow]Found {len(markets)} markets but none have complete CLOB and forecast data.[/bold yellow]")
        else:
            # Create Table for console output
            table = Table(title=f"Weather Markets: {city} ({len(complete_markets)} with complete data)", show_header=True, header_style="bold magenta", expand=True)
            table.add_column("Question", style="dim", no_wrap=False, max_width=45)
            table.add_column("Liq", justify="right", width=7)
            table.add_column("YES % (VWAP)", justify="right", style="bright_green", width=12)
            table.add_column("NO % (VWAP)", justify="right", style="bright_red", width=11)
            table.add_column("Resolves (UTC)", justify="center", style="cyan", width=14)
            table.add_column("Forecast @ (UTC)", justify="center", style="magenta", width=14)
            table.add_column("Temp Forecast", justify="center", style="yellow", width=15)

            for m in complete_markets:
                yes_book = m.get("yes_book") or {}
                no_book = m.get("no_book") or {}
                forecast = m.get("forecast_at_resolution")
                
                # Get volume-weighted prices (now stored in best_bid/best_ask)
                yes_vwap = yes_book.get('best_bid', 0)  # VWAP stored here now
                no_vwap = no_book.get('best_bid', 0)    # VWAP stored here now
                
                # Calculate fair value
                yes_fair = yes_vwap if yes_vwap > 0 else 0.5
                no_fair = no_vwap if no_vwap > 0 else 0.5
                
                # Format resolution time with AM/PM
                resolution_time = "N/A"
                if m.get("end_date"):
                    try:
                        dt = datetime.fromisoformat(m["end_date"].replace('Z', '+00:00'))
                        resolution_time = dt.strftime("%b %d %I:%M%p")
                    except:
                        resolution_time = m["end_date"][:16]
                
                # Format forecast time with AM/PM
                forecast_time = "N/A"
                if forecast and forecast.get("time"):
                    try:
                        dt = datetime.fromisoformat(forecast["time"].replace('Z', '+00:00'))
                        forecast_time = dt.strftime("%b %d %I:%M%p")
                    except:
                        forecast_time = forecast["time"][:16]
                
                # Format forecast temperature
                temp_c = forecast['temperature_c']
                temp_f = forecast['temperature_f']
                forecast_str = f"{temp_c}°C/{temp_f}°F"
                
                table.add_row(
                    m["question"],
                    f"${m['liquidity']/1000:.1f}k",
                    f"{yes_fair*100:.0f}%",
                    f"{no_fair*100:.0f}%",
                    resolution_time,
                    forecast_time,
                    forecast_str
                )
            
            console.print(table)
            console.print(f"\n[dim]Prices shown are volume-weighted fair values from order book depth.[/dim]")
        
        # Save to JSON (save all markets, not just complete ones)
        save_test_result(f"weather_search_{city.lower().replace(' ', '_')}", markets)
    
    await client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search Polymarket Weather Markets")
    parser.add_argument("city", nargs="?", default="London", help="City to search for (default: London)")
    parser.add_argument("--query", default="temperature", help="Keywords to search for")
    
    args = parser.parse_args()
    
    asyncio.run(run_standalone_search(args.city, args.query))
