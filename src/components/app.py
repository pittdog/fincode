"""Main Textual application for FinCode."""
import asyncio
from typing import Optional
from textual.app import ComposeResult, on
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Input, RichLog, Label
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel

from src.agent.agent import Agent
from src.agent.types import AgentConfig, AgentEvent


class IntroPanel(Static):
    """Introduction panel showing current model and status."""

    def __init__(self, model: str, provider: str):
        super().__init__()
        self.model = model
        self.provider = provider

    def render(self) -> Panel:
        """Render the intro panel."""
        intro_text = f"""[bold cyan]FinCode[/bold cyan] - Financial Research Agent

[yellow]Model:[/yellow] {self.model}
[yellow]Provider:[/yellow] {self.provider}

Type your financial research query and press Enter.
Use [bold]/model[/bold] to change models, [bold]exit[/bold] to quit."""

        return Panel(intro_text, title="[bold]Welcome[/bold]")


class QueryInput(Input):
    """Input widget for user queries."""

    def __init__(self):
        super().__init__(id="query_input")
        self.history: list[str] = []
        self.history_index = -1

    def action_history_up(self) -> None:
        """Navigate up in history."""
        if self.history and self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.value = self.history[-(self.history_index + 1)]

    def action_history_down(self) -> None:
        """Navigate down in history."""
        if self.history_index > 0:
            self.history_index -= 1
            self.value = self.history[-(self.history_index + 1)]
        elif self.history_index == 0:
            self.history_index = -1
            self.value = ""

    def add_to_history(self, query: str) -> None:
        """Add query to history."""
        self.history.insert(0, query)
        self.history_index = -1


class OutputLog(RichLog):
    """Output log for displaying results."""

    def __init__(self):
        super().__init__(id="output_log")


class FinCodeApp:
    """Main FinCode application."""

    def __init__(self, model: str = "gpt-4.1-mini", provider: str = "openai"):
        self.model = model
        self.provider = provider
        self.agent: Optional[Agent] = None
        self.chat_history: list[dict] = []
        self.is_processing = False

    async def initialize(self):
        """Initialize the agent."""
        config = AgentConfig(model=self.model, model_provider=self.provider)
        self.agent = Agent.create(config)

    async def process_query(self, query: str) -> str:
        """Process a user query and return the answer."""
        if not self.agent:
            return "Agent not initialized"

        self.chat_history.append({"role": "user", "content": query})
        answer = ""

        async for event in self.agent.run(query, self.chat_history):
            if isinstance(event, dict):
                event_type = event.get("type")
                if event_type == "tool_start":
                    print(f"🔧 Using {event.get('tool')}...")
                elif event_type == "tool_end":
                    print(f"✓ {event.get('tool')} completed")
                elif event_type == "answer_chunk":
                    answer += event.get("chunk", "")
                elif event_type == "done":
                    answer = event.get("answer", "")

        self.chat_history.append({"role": "assistant", "content": answer})
        return answer

    async def run(self):
        """Run the application."""
        await self.initialize()

        print("\n[bold cyan]FinCode[/bold cyan] - Financial Research Agent")
        print(f"[yellow]Model:[/yellow] {self.model}")
        print(f"[yellow]Provider:[/yellow] {self.provider}")
        print("\nType your financial research query and press Enter.")
        print("Use [bold]/model[/bold] to change models, [bold]exit[/bold] to quit.\n")

        while True:
            try:
                query = input("You: ").strip()

                if not query:
                    continue

                if query.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break

                if query == "/model":
                    print("Model selection not yet implemented in CLI mode")
                    continue

                print("\n[yellow]Researching...[/yellow]")
                self.is_processing = True

                answer = await self.process_query(query)

                print(f"\n[bold cyan]FinCode:[/bold cyan]\n{answer}\n")
                self.is_processing = False

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"[red]Error: {str(e)}[/red]")
                self.is_processing = False
