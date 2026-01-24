#!/usr/bin/env python3
"""Main entry point for FinCode TUI."""
import os
from pathlib import Path
from dotenv import load_dotenv
from components.app import FinCodeApp


def main():
    """Main entry point."""
    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Get model and provider from environment or use defaults
    model = os.getenv("MODEL", "grok-3")
    provider = os.getenv("MODEL_PROVIDER", "xai")

    # Create and run app
    app = FinCodeApp(model=model, provider=provider)
    app.run()


if __name__ == "__main__":
    main()
