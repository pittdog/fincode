"""Simplified CLI interface for FinCode."""
import asyncio
from typing import Optional, List, Dict
from rich.console import Console
from rich.markdown import Markdown

from agent.agent import Agent
from agent.types import (
    AgentConfig, AgentEvent, ToolStartEvent, ToolEndEvent,
    AnswerChunkEvent, DoneEvent, LogEvent
)


class FinCodeCLI:
    """CLI application for FinCode."""

    def __init__(self, model: str = "grok-3", provider: str = "xai"):
        self.model = model
        self.provider = provider
        self.agent: Optional[Agent] = None
        self.chat_history: List[Dict[str, str]] = []
        self.console = Console()

    async def initialize(self):
        """Initialize the agent."""
        config = AgentConfig(model=self.model, model_provider=self.provider)
        self.agent = Agent.create(config)

    async def process_query(self, query: str):
        """Process a user query and stream results to console."""
        if not self.agent:
            self.console.print("[red]Agent not initialized[/red]")
            return

        self.chat_history.append({"role": "user", "content": query})
        
        async for event in self.agent.run(query, self.chat_history):
            if isinstance(event, LogEvent):
                if event.level == "thought":
                    self.console.print(f"\n[italic blue]> Thought: {event.message.strip()}[/italic blue]")
                elif event.level == "tool":
                    self.console.print(f"🔧 [bold yellow]Action:[/bold yellow] {event.message}")
                else:
                    self.console.print(f"ℹ️ {event.message}")
            
            elif isinstance(event, ToolStartEvent):
                self.console.print(f"🔧 Using [bold cyan]{event.tool}[/bold cyan]...")
            elif isinstance(event, ToolEndEvent):
                self.console.print(f"✓ [bold green]{event.tool}[/bold green] completed")
            elif isinstance(event, AnswerChunkEvent):
                # We could stream chunky answers, but for now we wait for Done
                pass
            elif isinstance(event, DoneEvent):
                self.console.print("\n[bold cyan]FinCode:[/bold cyan]")
                self.console.print(Markdown(event.answer))
                self.chat_history.append({"role": "assistant", "content": event.answer})

    async def run(self):
        """Run the CLI interactive loop."""
        await self.initialize()

        self.console.print("\n[bold cyan]FinCode CLI[/bold cyan] - Financial Research Agent")
        self.console.print(f"[yellow]Model:[/yellow] {self.model}")
        self.console.print(f"[yellow]Provider:[/yellow] {self.provider}\n")

        while True:
            try:
                query = self.console.input("[bold green]You:[/bold green] ").strip()

                if not query:
                    continue

                if query.lower() in ["exit", "quit"]:
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break

                self.console.print("\n[yellow]Researching...[/yellow]")
                await self.process_query(query)
                self.console.print("")

            except KeyboardInterrupt:
                self.console.print("\n\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
