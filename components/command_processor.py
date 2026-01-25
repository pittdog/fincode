import os
import sys
import json
from typing import Optional, Dict, Any, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

class CommandProcessor:
    """Processes OpenBB-style commands directly for speed (bash-style) or yields to agent."""

    def __init__(self, agent_instance):
        self.agent = agent_instance
        self.console = Console()
        self.current_ticker: Optional[str] = None
        self.history: List[str] = []

    async def process_command(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Processes a command directly if possible.
        Returns (is_handled, agent_query).
        """
        parts = user_input.strip().lower().split()
        if not parts:
            return True, None

        cmd = parts[0]
        args = parts[1:]

        # Global basic commands
        if cmd in ["help", "h", "?"]:
            self._show_help()
            return True, None
        elif cmd == "cls":
            os.system('cls' if os.name == 'nt' else 'clear')
            return True, None
        elif cmd in ["exit", "q"]:
            self.console.print("[yellow]Exiting FinCode...[/yellow]")
            sys.exit(0)
        elif cmd == "reset" or cmd == "r" or user_input == "..":
            self.current_ticker = None
            self.console.print("[green]Context reset.[/green]")
            return True, None

        # Data commands - Direct Execution!
        if cmd == "load":
            if not args:
                self.console.print("[red]Error: Specify ticker (e.g., load AAPL)[/red]")
                return True, None
            ticker = args[0].upper()
            self.current_ticker = ticker
            self.console.print(f"Loading [bold cyan]{ticker}[/bold cyan] details...")
            
            result = await self._exec_tool("get_ticker_details", ticker=ticker)
            self._display_data(f"{ticker} Profile", result)
            return True, None

        elif cmd == "news":
            ticker = args[0].upper() if args else self.current_ticker
            if not ticker:
                self.console.print("[red]Error: No ticker loaded/specified.[/red]")
                return True, None
            self.console.print(f"Fetching news for [bold cyan]{ticker}[/bold cyan]...")
            
            result = await self._exec_tool("get_news", query=ticker)
            self._display_data(f"{ticker} News", result)
            return True, None

        elif cmd == "financials":
            ticker = args[0].upper() if args else self.current_ticker
            if not ticker:
                self.console.print("[red]Error: No ticker loaded/specified.[/red]")
                return True, None
            
            # Default to income statement for quick view
            self.console.print(f"Fetching financials for [bold cyan]{ticker}[/bold cyan]...")
            result = await self._exec_tool("get_financials", ticker=ticker, statement_type="income")
            self._display_data(f"{ticker} Financials", result)
            return True, None

        elif cmd == "quote":
             ticker = args[0].upper() if args else self.current_ticker
             if not ticker:
                 self.console.print("[red]Error: No ticker loaded/specified.[/red]")
                 return True, None
             self.console.print(f"Fetching quote for [bold cyan]{ticker}[/bold cyan]...")
             result = await self._exec_tool("get_ticker_details", ticker=ticker)
             self._display_data(f"{ticker} Quote", result)
             return True, None

        # Polymarket Commands
        elif cmd.startswith("poly:"):
            if cmd == "poly:backtest":
                subcmd = args[0] if args else "weather"
                period = args[1] if len(args) > 1 else "week"
                
                self.console.print(f"[bold cyan]Running Polymarket Backtest: {subcmd} ({period})[/bold cyan]")
                
                try:
                    import asyncio
                    from utils.backtests.real_backtest_util import run_real_backtest
                    
                    # Ensure API keys are present
                    tomorrow_io_key = os.getenv("TOMORROWIO_API_KEY")
                    if not tomorrow_io_key:
                        self.console.print("[red]Error: TOMORROWIO_API_KEY not set.[/red]")
                        return True, None
                    
                    # Run the backtest (direct await for the async call)
                    results = await run_real_backtest(
                        tomorrow_io_key=tomorrow_io_key,
                        output_dir="test-results"
                    )
                        
                    self._display_data("Backtest Results", results)
                except Exception as e:
                    self.console.print(f"[red]Error running backtest: {e}[/red]")
                return True, None

            elif cmd == "poly:weather":
                if args:
                    query = " ".join(args)
                    self.console.print(f"[bold cyan]Searching Polymarket for: {query}[/bold cyan]")
                    result = await self._exec_tool("search_weather_markets", query=query)
                    self._display_data(f"Weather Search: {query}", result)
                else:
                    self.console.print(f"[bold cyan]Scanning Polymarket Weather Opportunities...[/bold cyan]")
                    result = await self._exec_tool("scan_weather_opportunities")
                    self._display_data("Weather Opportunities", result)
                return True, None

            elif cmd == "poly:buy":
                if len(args) < 2:
                    self.console.print("[red]Error: Usage: poly:buy <amount> <market_id>[/red]")
                    return True, None
                amount = args[0]
                market_id = args[1]
                self.console.print(f"[bold cyan]Simulating Buy: {amount} on {market_id}[/bold cyan]")
                # Place holder for wrapper.simulate_trade(...)
                result = await self._exec_tool("simulate_polymarket_trade", amount=amount, market_id=market_id)
                self._display_data("Trade Simulation", result)
                return True, None

        # If it doesn't match a direct shortcut, it might be a complex command for the agent
        # or just a natural language question.
        return False, user_input

    async def _exec_tool(self, tool_name: str, **kwargs) -> Any:
        """Call a tool function directly from the agent's tool_map."""
        if tool_name not in self.agent.tool_map:
            return {"error": f"Tool {tool_name} not available"}
        
        try:
            tool = self.agent.tool_map[tool_name]
            # StructuredTool.func is the raw method
            import inspect
            if inspect.iscoroutinefunction(tool.func):
                return await tool.func(**kwargs)
            else:
                return tool.func(**kwargs)
        except Exception as e:
            return {"error": str(e)}

    def _display_data(self, title: str, data: Any):
        """Standardized data display for direct commands."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass
        
        if isinstance(data, dict) and "error" in data:
            self.console.print(f"[red]Error:[/red] {data['error']}")
            return

        # Special handling for Ticker Profile / Quote
        if isinstance(data, dict) and "market_cap" in data and "description" in data:
            ticker = data.get("ticker", "N/A")
            name = data.get("name", "N/A")
            market_cap = f"${data['market_cap']:,}" if isinstance(data.get("market_cap"), (int, float)) else "N/A"
            
            # Extract price data if available
            price = data.get("price_data", {})
            day = price.get("day", {})
            prev = price.get("prevDay", {})
            
            # Key Stats Table
            stats = Table(show_header=False, box=None, padding=(0, 2))
            
            # Format price row if available
            if day.get("c"):
                current_price = f"${day['c']:.2f}"
                change = price.get("todaysChange", 0)
                change_perc = price.get("todaysChangePerc", 0)
                color = "green" if change >= 0 else "red"
                sign = "+" if change >= 0 else ""
                stats.add_row("[bold cyan]Price:[/bold cyan]", f"[bold {color}]{current_price} ({sign}{change:.2f}, {sign}{change_perc:.2f}%)[/bold {color}]")

            stats.add_row("[bold cyan]Previous Close:[/bold cyan]", f"${prev['c']:.2f}" if prev.get("c") else "N/A")
            stats.add_row("[bold cyan]Open:[/bold cyan]", f"${day['o']:.2f}" if day.get("o") else "N/A")
            
            if day.get("l") and day.get("h"):
                stats.add_row("[bold cyan]Day Range:[/bold cyan]", f"${day['l']:.2f} - ${day['h']:.2f}")

            stats.add_row("[bold cyan]Market Cap:[/bold cyan]", market_cap)
            
            if day.get("v"):
                stats.add_row("[bold cyan]Volume:[/bold cyan]", f"{day['v']:,}")

            stats.add_row("[bold cyan]Exchange:[/bold cyan]", data.get("primary_exchange", "N/A"))
            stats.add_row("[bold cyan]Website:[/bold cyan]", data.get("homepage_url", "N/A"))
            
            # Shared outstanding
            shares = f"{data.get('share_class_shares_outstanding', 0):,}" if data.get("share_class_shares_outstanding") else "N/A"
            stats.add_row("[bold cyan]Shares Out:[/bold cyan]", shares)
            
            updated_ts = price.get("updated")
            if updated_ts:
                # Convert nanoseconds to string
                from datetime import datetime
                try:
                    ts = datetime.fromtimestamp(updated_ts / 1e9).strftime('%Y-%m-%d %H:%M:%S')
                    stats.add_row("[bold cyan]Last Updated:[/bold cyan]", ts)
                except:
                    pass

            self.console.print(f"\n[bold green]{name} ({ticker})[/bold green]")
            self.console.print(Panel(stats, title="[bold]Market Data & Key Stats[/bold]", border_style="cyan"))
            
            self.console.print(Panel(
                data.get("description", "No description available."),
                title="[bold]Business Description[/bold]",
                border_style="blue",
                padding=(1, 2)
            ))
            self.console.print(f"[dim italic]Source: Massive[/dim italic]")
            return

        # Special handling for News results to quote sources and provider
        if isinstance(data, dict) and "results" in data and "provider" in data:
            self.console.print(f"\n[bold green]Provider: {data['provider']}[/bold green]")
            for item in data["results"]:
                title_text = item.get("title", "No Title")
                summary = item.get("summary", item.get("content", ""))
                source = item.get("source", item.get("url", "N/A"))
                timestamp = item.get("timestamp", "N/A")
                
                self.console.print(Panel(
                    f"{summary}\n\n[bold italic]Source:[/bold italic] {source}\n[bold italic]Time:[/bold italic] {timestamp}",
                    title=f"[bold]{title_text}[/bold]",
                    border_style="blue"
                ))
            return

        # Special handling for Financials (Tabular)
        if isinstance(data, dict) and any(k in data for k in ["revenues", "net_income_loss", "assets", "liabilities"]):
            meta = data.pop("_metadata", {})
            end_date = meta.get("end_date", "N/A")
            period = f"{meta.get('fiscal_year', '')} {meta.get('fiscal_period', '')}".strip()
            
            table = Table(
                title=f"[bold green]{title}[/bold green] (Cut-off: {end_date} | {period})",
                show_header=True,
                header_style="bold cyan"
            )
            table.add_column("Line Item", style="dim")
            table.add_column("Value", justify="right")
            
            for key, val in data.items():
                if isinstance(val, dict) and "value" in val:
                    display_val = f"{val['value']:,}" if isinstance(val['value'], (int, float)) else str(val['value'])
                    unit = val.get("unit", "")
                    table.add_row(key.replace("_", " ").title(), f"{display_val} {unit}")
            
            self.console.print(table)
            self.console.print(f"[dim italic]Source: Massive (Polygon)[/dim italic]")
            return

        pretty_json = json.dumps(data, indent=2)
        panel = Panel(
            Syntax(pretty_json, "json", theme="monokai", word_wrap=True),
            title=f"[bold green]{title}[/bold green]",
            border_style="cyan"
        )
        self.console.print(panel)

    def _show_help(self):
        table = Table(title="FinCode Global Commands (BASH-STYLE)", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="bold yellow")
        table.add_column("Description")
        table.add_column("Speed", style="italic green")

        table.add_row("load <ticker>", "Direct profile lookup (Massive)", "Instant")
        table.add_row("news [ticker]", "Direct news lookup (xAI/Grok)", "Instant")
        table.add_row("financials [ticker]", "Direct financials lookup (Massive/Polygon)", "Instant")
        table.add_row("quote [ticker]", "Real-time quote data", "Instant")
        table.add_row("poly:backtest [type] [period]", "Run Polymarket backtest (Real data)", "Slow")
        table.add_row("poly:weather", "Scan for weather opportunities", "Instant")
        table.add_row("poly:buy <amt> <id>", "Simulate CLOB buy trade", "Instant")
        table.add_row("reset, r, ..", "Reset context/ticker", "-")
        table.add_row("help, h, ?", "Displays this menu", "-")
        table.add_row("cls", "Clear screen", "-")
        table.add_row("exit, q", "Quit application", "-")
        
        self.console.print(table)
        self.console.print("\n[italic]Note: Any other input is handled by the AI Research Agent (LangGraph).[/italic]")
