from textual.app import App, ComposeResult
from textual.widgets import Button, Footer, Header, Input, Static, Label
from textual.containers import Container, Horizontal, Vertical
import httpx
import asyncio
import json

API_URL = "http://127.0.0.1:8000"  # Change to your server IP when running on mobile

class ThinTUI(App):
    """A thin client for FinCode running on Textual."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #input-container {
        height: auto;
        margin: 1 1;
    }
    
    #button-container {
        height: auto;
        margin: 1 1;
        align: center middle;
    }
    
    Button {
        margin: 0 1;
    }
    
    #result {
        height: 1fr;
        border: solid green;
        margin: 1 1;
        padding: 1 1;
        overflow-y: scroll;
    }
    
    .error {
        border: solid red;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("City:"),
            Input(placeholder="Enter city (e.g. London)", id="city_input"),
            id="input-container"
        )
        yield Horizontal(
            Button("Get Weather", id="btn_weather", variant="primary"),
            Button("Predict Market", id="btn_predict", variant="warning"),
            id="button-container"
        )
        yield Static("Ready.", id="result")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        city = self.query_one("#city_input", Input).value.strip() or "London"
        result_widget = self.query_one("#result", Static)
        
        if event.button.id == "btn_weather":
            result_widget.update(f"Fetching weather for {city}...")
            asyncio.create_task(self.fetch_weather(city))
            
        elif event.button.id == "btn_predict":
            result_widget.update(f"Running prediction for {city} (may take a moment)...")
            asyncio.create_task(self.fetch_prediction(city))

    async def fetch_weather(self, city: str):
        result_widget = self.query_one("#result", Static)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{API_URL}/weather", json={"city": city, "days": 7})
                if resp.status_code == 200:
                    data = resp.json()
                    formatted = json.dumps(data, indent=2)
                    result_widget.update(formatted)
                    result_widget.remove_class("error")
                else:
                    result_widget.update(f"Error: {resp.status_code}\n{resp.text}")
                    result_widget.add_class("error")
        except Exception as e:
            result_widget.update(f"Connection Error: {str(e)}")
            result_widget.add_class("error")

    async def fetch_prediction(self, city: str):
        result_widget = self.query_one("#result", Static)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for analysis
                resp = await client.post(f"{API_URL}/predict", json={"city": city, "days": 7, "lookback_days": 7})
                if resp.status_code == 200:
                    data = resp.json()
                    formatted = json.dumps(data, indent=2)
                    result_widget.update(formatted)
                    result_widget.remove_class("error")
                else:
                    result_widget.update(f"Error: {resp.status_code}\n{resp.text}")
                    result_widget.add_class("error")
        except Exception as e:
            result_widget.update(f"Connection Error: {str(e)}")
            result_widget.add_class("error")

if __name__ == "__main__":
    app = ThinTUI()
    app.run()
