#!/usr/bin/env python3
"""Main entry point for FinCode."""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
from components.app import FinCodeApp


async def main():
    """Main entry point."""
    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Get model and provider from environment or use defaults
    model = os.getenv("MODEL", "gpt-4.1-mini")
    provider = os.getenv("MODEL_PROVIDER", "openai")

    # Create and run app
    app = FinCodeApp(model=model, provider=provider)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
