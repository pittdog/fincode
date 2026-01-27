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
        from utils.portfolio_manager import PortfolioManager
        from agent.tools.polymarket_tool import get_polymarket_client
        self.portfolio = PortfolioManager()
        self._pm_client_cache = None

    async def process_command(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Processes a command directly if possible.
        Returns (is_handled, agent_query).
        """
        raw_parts = user_input.strip().split()
        if not raw_parts:
            return True, None

        cmd = raw_parts[0].lower()
        args = raw_parts[1:]

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

        elif user_input.strip().lower().startswith("poly:"):
            full_input = user_input.strip()
            if full_input.lower().startswith("poly: "):
                # Extract original case for args
                effective_cmd = "poly:" + full_input[6:].strip().split()[0].lower() if len(full_input) > 6 else "poly:"
                effective_args = full_input[6:].strip().split()[1:] if len(full_input) > 6 else []
            else:
                effective_cmd = cmd
                effective_args = args

            # Handle poly:backtest
            if effective_cmd == "poly:backtest":
                if not effective_args:
                    self.console.print("[red]Error: Usage: poly:backtest <city> <numdays>[/red]")
                    self.console.print("Example: poly:backtest Seoul 1")
                    return True, None
                
                # Parse arguments: Handle multi-word cities, numdays, and optional DATE
                # Format: poly:backtest <city> [numdays] [date]
                
                from datetime import datetime
                numdays = 7  # Default
                target_date = datetime.now().strftime("%Y-%m-%d")
                
                # Copy args to consume
                args_to_parse = effective_args.copy()
                
                # 1. Check for Date at the end (YYYY-MM-DD)
                if args_to_parse and len(args_to_parse[-1]) == 10 and args_to_parse[-1].count('-') == 2:
                    target_date = args_to_parse.pop()
                    
                # 2. Check for NumDays at the end (after date removed)
                if args_to_parse and args_to_parse[-1].isdigit():
                    numdays = int(args_to_parse.pop())
                
                # 3. Remaining is City
                if not args_to_parse:
                     self.console.print("[red]Error: City name is required.[/red]")
                     return True, None
                     
                raw_city = " ".join(args_to_parse).replace('"', '').replace("'", "")
                
                # Handle standard casing unless it's an acronym
                if raw_city.upper() in ["NYC", "LA", "DC", "SF", "NYC."]:
                    city = raw_city.upper()
                else:
                    city = raw_city.title()
                
                self.console.print(f"[bold cyan]Running Cross-Sectional Backtest for {city} on {target_date} for {numdays} days...[/bold cyan]")
                
                # Run backtest
                await self._run_backtest_handler(city, target_date, numdays)
                return True, None

            # Handle poly:weather (with fuzzy matching for typos like 'weathter')
            elif any(x in effective_cmd or (effective_args and x in effective_args[0]) for x in ["weather", "weathter", "wether"]):
                # If they typed 'poly: weather' then args[0] might be the city
                # If they typed 'poly:weather London' then effective_cmd is 'poly:weather' and args[0] is 'London'
                # If they typed 'poly: weather London' then effective_cmd is 'poly:weather' and args is ['London']
                
                # Re-parse city correctly
                if effective_cmd == "poly:weather" or effective_cmd == "poly:weathter" or effective_cmd == "poly:wether":
                    city = " ".join(effective_args)
                else:
                    # Case like 'poly: weather London' where effective_cmd was parsed as 'poly:weather' already
                    city = " ".join(effective_args)

                query = "temperature"
                if city:
                    self.console.print(f"[bold cyan]Searching Polymarket Weather for:[/bold cyan] [yellow]{city}[/yellow]")
                    result = await self._exec_tool("search_weather_markets", query=query, city=city)
                else:
                    self.console.print(f"[bold cyan]Scanning Polymarket Weather Opportunities...[/bold cyan]")
                    result = await self._exec_tool("search_weather_markets", query=query)
                
                self._display_weather_markets(result, city or "All Cities")
                return True, None

            elif effective_cmd == "poly:predict":
                if not effective_args:
                    self.console.print("[red]Error: Usage: poly:predict <city> <numdays>[/red]")
                    self.console.print("Example: poly:predict London 2")
                    return True, None
                
                city = effective_args[0].title()
                try:
                    numdays = int(effective_args[1]) if len(effective_args) > 1 else 2
                except ValueError:
                    numdays = 2
                
                # Determine date range for prediction (tomorrow onwards)
                from datetime import datetime, timedelta
                today = datetime.now()
                # For prediction, we want future dates. 
                # run_backtest takes a target_date and lookback_days.
                # If we pass target_date = "tomorrow + numdays" and lookback_days = numdays,
                # it will iterate from target_date down to target_date - lookback.
                # Example: Predict 2 days. 
                # If today is 26th. 
                # We want 27th, 28th.
                # Set target = 28th. lookback = 1 (so 28, 27).
                
                target_date_obj = today + timedelta(days=numdays)
                target_date = target_date_obj.strftime("%Y-%m-%d")
                self.console.print(f"[bold cyan]Running Prediction for {city} (Next {numdays} days)...[/bold cyan]")
                
                # Run prediction using same engine
                await self._run_backtest_handler(city, target_date, numdays, is_prediction=True)
                return True, None

            elif effective_cmd == "poly:buy":
                if len(effective_args) < 2:
                    self.console.print("[red]Error: Usage: poly:buy <amount> <market_id>[/red]")
                    return True, None
                amount = effective_args[0]
                market_id = effective_args[1]
                self.console.print(f"[bold cyan]Simulating Buy: {amount} on {market_id}[/bold cyan]")
                result = await self._exec_tool("simulate_polymarket_trade", amount=amount, market_id=market_id)
                self._display_data("Trade Simulation", result)
                return True, None

            elif effective_cmd == "poly:paperbuy":
                if len(effective_args) < 2:
                    self.console.print("[red]Error: Usage: poly:paperbuy <amount> <market_id>[/red]")
                    return True, None
                
                try:
                    amount = float(effective_args[0])
                    market_id = effective_args[1]
                except ValueError:
                    self.console.print("[red]Error: Amount must be a number.[/red]")
                    return True, None
                
                self.console.print(f"Fetching current price for [yellow]{market_id}[/yellow]...")
                if not self._pm_client_cache:
                    from agent.tools.polymarket_tool import get_polymarket_client
                    self._pm_client_cache = await get_polymarket_client()
                
                market = await self._pm_client_cache.get_market_by_id(market_id)
                
                if not market:
                    self.console.print(f"[red]Error: Could not find market {market_id}[/red]")
                    return True, None
                
                # Market is a PolymarketMarket object
                price = market.yes_price
                if price <= 0:
                    self.console.print("[red]Error: Market has no valid price.[/red]")
                    return True, None
                
                trade = self.portfolio.add_trade(market_id, market.question, amount, price)
                self.console.print(Panel(
                    f"Market: {market.question}\nEntry Price: [bold]${price:.3f}[/bold]\nAmount: [green]${amount:.2f}[/green]\nShares: [cyan]{trade['shares']:.2f}[/cyan]",
                    title="[bold green]Paper Trade Executed[/bold green]",
                    border_style="green"
                ))
                return True, None

            elif effective_cmd == "poly:papersell":
                if len(effective_args) < 1:
                    self.console.print("[red]Error: Usage: poly:papersell <transaction_id>[/red]")
                    return True, None
                
                trade_id = effective_args[0]
                
                # Check if trade exists and is open
                trades = self.portfolio.get_trades()
                target_trade = None
                for t in trades:
                    if t["id"] == trade_id or t["id"].endswith(trade_id):
                        if t["status"] == "OPEN":
                            target_trade = t
                            break
                        else:
                            self.console.print(f"[yellow]Trade {trade_id} is already SOLD.[/yellow]")
                            return True, None
                
                if not target_trade:
                    self.console.print(f"[red]Error: Open trade with ID {trade_id} not found.[/red]")
                    return True, None
                
                self.console.print(f"Closing trade {trade_id} at current market price...")
                if not self._pm_client_cache:
                    from agent.tools.polymarket_tool import get_polymarket_client
                    self._pm_client_cache = await get_polymarket_client()
                
                market = await self._pm_client_cache.get_market_by_id(target_trade["market_id"])
                if not market:
                    self.console.print("[red]Error: Could not fetch current market price to close trade.[/red]")
                    return True, None
                
                exit_price = market.yes_price
                closed_trade = self.portfolio.close_trade_by_id(trade_id, exit_price)
                
                if closed_trade:
                    pnl = closed_trade["payout"] - closed_trade["amount"]
                    pnl_perc = (pnl / closed_trade["amount"] * 100) if closed_trade["amount"] > 0 else 0
                    pnl_color = "green" if pnl >= 0 else "red"
                    
                    self.console.print(Panel(
                        f"Market: {closed_trade['question']}\n"
                        f"Exit Price: [bold]${exit_price:.3f}[/bold]\n"
                        f"Payout: [green]${closed_trade['payout']:.2f}[/green]\n"
                        f"PnL: [{pnl_color}]${pnl:+.2f} ({pnl_perc:+.2f}%)[/{pnl_color}]",
                        title="[bold yellow]Paper Trade SOLD[/bold yellow]",
                        border_style="yellow"
                    ))
                return True, None

            elif effective_cmd == "poly:portfolio":
                await self._display_portfolio()
                return True, None
            
            else:
                self.console.print(f"[red]Unknown Polymarket command: {effective_cmd}[/red]")
                self.console.print("Available: poly:weather, poly:backtest, poly:buy")
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
            self.console.print(f"Source: Massive")
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
            self.console.print(f"Source: Massive (Polygon)")
            return

        pretty_json = json.dumps(data, indent=2)
        panel = Panel(
            Syntax(pretty_json, "json", theme="monokai", word_wrap=True),
            title=f"[bold green]{title}[/bold green]",
            border_style="cyan"
        )
        self.console.print(panel)

    def _display_weather_markets(self, markets: Any, city: str):
        """Display weather markets in a formatted table."""
        from datetime import datetime
        
        if not markets or not isinstance(markets, list):
            self.console.print(f"[bold red]No weather markets found for {city}.[/bold red]")
            return
        
        # Filter markets to only show those with complete data (no N/As)
        complete_markets = [
            m for m in markets 
            if m.get("yes_book") and m.get("yes_book").get("best_bid") is not None
            and m.get("forecast_at_resolution")
        ]
        
        if not complete_markets:
            self.console.print(f"[bold yellow]Found {len(markets)} markets but none have complete CLOB and forecast data.[/bold yellow]")
            self.console.print(f"Markets without forecasts cannot be analyzed for edge opportunities.")
            return
        
        # Create Table for console output
        table = Table(
            title=f"Weather Markets: {city} ({len(complete_markets)} with complete data)", 
            show_header=True, 
            header_style="bold magenta",
            expand=True
        )
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
        
        self.console.print(table)
        self.console.print(f"\nPrices shown are volume-weighted fair values from order book depth.")

    async def _run_backtest_handler(self, city: str, date: str, lookback_days: int = 7, is_prediction: bool = False):
        """Async handler for running backtest to avoid blocking the CLI loop."""
        try:
            from utils.backtest_engine import BacktestEngine
            from agent.tools.polymarket_tool import PolymarketClient
            from agent.tools.visual_crossing_client import VisualCrossingClient
            
            pm_client = PolymarketClient()
            vc_client = VisualCrossingClient()
            engine = BacktestEngine(pm_client, vc_client)
            
            if is_prediction:
                print(f"Fetching forecast data for {city}...")
            
            result = await engine.run_backtest(city, date, lookback_days, is_prediction=is_prediction)
            
            if not result.get("success"):
                self.console.print(f"\n[red]Backtest Failed: {result.get('error')}[/red]")
                await pm_client.close()
                await vc_client.close()
                return

            # Display Trade Details Table
            if result.get("trades"):
                title = f"Market Prediction '{result['city']}'" if is_prediction else f"Market Backtest '{result['city']}'"
                self.console.print(f"\n[bold green]{title}[/bold green]")
                
                trade_table = Table(show_header=True, header_style="bold cyan")
                trade_table.add_column("Date", style="dim", width=8)
                trade_table.add_column("Target", justify="center", ratio=2)
                trade_table.add_column("Fcst", justify="center", style="magenta")
                if is_prediction:
                    trade_table.add_column("Market ID", style="cyan", width=8)
                trade_table.add_column("Our %", justify="right", width=6)
                trade_table.add_column("Mkt %", justify="right", width=6)
                trade_table.add_column("Price", justify="right")
                trade_table.add_column("Ends In", justify="right", style="dim")
                trade_table.add_column("Result", justify="center")

                for t in result["trades"]:
                    res_color = "green" if t["result"] == "WIN" else "red" if t["result"] == "LOSS" else "yellow"
                    # Compact Date: Jan 28
                    from datetime import datetime
                    try:
                        date_display = datetime.strptime(t["date"], "%Y-%m-%d").strftime("%b %d")
                    except:
                        date_display = t["date"]

                    row_data = [
                        date_display,
                        f"{t['bucket']} ({t['target_f']}°F)",
                        f"{t['forecast']}°F",
                    ]
                    
                    if is_prediction:
                        row_data.append(str(t.get("market_id", "N/A")))
                        
                    row_data.extend([
                        t["prob"],
                        t.get("market_prob", "N/A"),
                        f"${t['price']:.3f}",
                        t.get("countdown", "N/A"),
                        f"[{res_color}]{t['result']}[/{res_color}]"
                    ])
                    
                    trade_table.add_row(*row_data)
                self.console.print(trade_table)
            else:
                markets_found = result.get("markets_found", 0)
                if markets_found > 0:
                     self.console.print(f"\n[bold yellow]Found {markets_found} relevant markets, but no trades met the strategy criteria (positive edge).[/bold yellow]")
                     self.console.print(f"[dim](This suggests the market prices were less attractive than the calculated fair values.)[/dim]")
                else:
                    self.console.print(f"\n[bold yellow]No active trades found for {result['city']} in the specified period.[/bold yellow]")
                    self.console.print(f"[dim](This usually means no 'Highest Temperature' markets match the dates on Polymarket.)[/dim]")

            # Display Summary Stats
            self.console.print("\n[bold]Portfolio Performance Summary:[/bold]")
            stats = Table(show_header=True, header_style="bold magenta")
            stats.add_column("Metric")
            stats.add_column("Value", justify="right")
            
            stats.add_row("Initial Bankroll", "$1000.00")
            stats.add_row("Completed Investments", f"${result['resolved_invested']:.2f}")
            stats.add_row("Total Payouts", f"${result['resolved_payout']:.2f}")
            
            pnl_color = "green" if result['resolved_roi'] >= 0 else "red"
            stats.add_row("Net Profit (Resolved)", f"[{pnl_color}]${(result['resolved_payout'] - result['resolved_invested']):.2f}[/{pnl_color}]")
            stats.add_row("Resolved ROI", f"[{pnl_color}]{result['resolved_roi']:.2f}%[/{pnl_color}]")
            
            if result.get("pending_invested", 0) > 0:
                stats.add_section()
                stats.add_row("Capital in Active Markets", f"[yellow]${result['pending_invested']:.2f}[/yellow]")
            
            self.console.print(stats)
            self.console.print(f"\nDetailed report saved to: {result['csv_path']}")

            await pm_client.close()
            await vc_client.close()
            
        except Exception as e:
            mode_label = "Analysis" if is_prediction else "Backtest"
            self.console.print(f"[red]Error running {mode_label}: {str(e)}[/red]")
            import traceback
            traceback.print_exc()

    async def _display_portfolio(self):
        """Display the current paper trading portfolio performance."""
        trades = self.portfolio.get_trades()
        if not trades:
            self.console.print("[yellow]Your portfolio is empty. Use poly:paperbuy to start trading![/yellow]")
            return

        table = Table(title="Paper Trading Portfolio", header_style="bold magenta")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Market", ratio=4)
        table.add_column("Entry", justify="right")
        table.add_column("Curr", justify="right")
        table.add_column("PnL", justify="right")
        table.add_column("Status", justify="center")

        total_invested = 0
        total_value = 0

        for t in trades:
            market_id = t["market_id"]
            entry_price = t["entry_price"]
            shares = t["shares"]
            invested = t["amount"]
            
            # For OPEN trades, get current price
            current_price = entry_price
            status_display = t["status"]
            
            if t["status"] == "OPEN":
                if not self._pm_client_cache:
                    from agent.tools.polymarket_tool import get_polymarket_client
                    self._pm_client_cache = await get_polymarket_client()
                
                market = await self._pm_client_cache.get_market_by_id(market_id)
                if market:
                    current_price = market.yes_price
                status_display = "[yellow]OPEN[/yellow]"
            else:
                current_price = t.get("exit_price") or (1.0 if t["payout"] > 0 else 0.0)
                status_display = "[green]SOLD[/green]" if t["payout"] > 0 else "[red]SOLD[/red]"

            value = shares * current_price
            pnl = value - invested
            pnl_perc = (pnl / invested * 100) if invested > 0 else 0
            pnl_color = "green" if pnl >= 0 else "red"
            
            total_invested += invested
            total_value += value

            table.add_row(
                t["id"][-6:], # Only show last 6 chars of ID
                t["question"],
                f"${entry_price:.3f}",
                f"${current_price:.3f}",
                f"[{pnl_color}]${pnl:+.2f} ({pnl_perc:+.1f}%)[/{pnl_color}]",
                status_display
            )

        self.console.print(table)
        
        # Summary footer
        total_pnl = total_value - total_invested
        total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        pnl_color = "green" if total_pnl >= 0 else "red"
        
        summary = Table.grid(padding=(0, 2))
        summary.add_column(justify="right", style="bold")
        summary.add_column(justify="left")
        summary.add_row("Total Invested:", f"${total_invested:.2f}")
        summary.add_row("Portfolio Value:", f"${total_value:.2f}")
        summary.add_row("Net Profit/Loss:", f"[{pnl_color}]${total_pnl:+.2f} ({total_pnl_perc:+.2f}%)[/{pnl_color}]")
        
        self.console.print(Panel(summary, title="[bold]Portfolio Summary[/bold]", border_style="cyan"))

    def _show_help(self):
        table = Table(title="FinCode Global Commands (BASH-STYLE)", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="bold yellow")
        table.add_column("Description")
        table.add_column("Speed", style="italic green")

        table.add_row("load <ticker>", "Direct profile lookup (Massive)", "Instant")
        table.add_row("news [ticker]", "Direct news lookup (xAI/Grok)", "Instant")
        table.add_row("financials [ticker]", "Direct financials lookup (Massive/Polygon)", "Instant")
        table.add_row("quote [ticker]", "Real-time quote data", "Instant")
        table.add_row("poly:backtest <city> <numdays>", "Multi-day Highest-Prob Backtest", "5-10s")
        table.add_row("poly:predict <city> <numdays>", "Multi-day Highest-Prob Prediction", "5-10s")
        table.add_row("poly:weather [city]", "Scan for weather opportunities or search by city", "Instant")
        table.add_row("poly:paperbuy <amt> <id>", "Simulate a trade in your paper portfolio", "Instant")
        table.add_row("poly:papersell <id>", "Sell an open paper trade by ID", "Instant")
        table.add_row("poly:portfolio", "View your paper trading performance", "Instant")
        table.add_row("poly:buy <amt> <id>", "Detailed simulation (no storage)", "Instant")
        table.add_row("reset, r, ..", "Reset context/ticker", "-")
        table.add_row("help, h, ?", "Displays this menu", "-")
        table.add_row("cls", "Clear screen", "-")
        table.add_row("exit, q", "Quit application", "-")
        
        self.console.print(table)
        self.console.print("\n[bold cyan]Examples:[/bold cyan]")
        self.console.print("  [yellow]poly:weather London[/yellow] - Search for London weather markets")
        self.console.print("  [yellow]poly:weather \"temperature New York\"[/yellow] - Detailed keyword search")
        self.console.print("\n[italic]Note: Any other input is handled by the AI Research Agent (LangGraph).[/italic]")
