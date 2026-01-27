#!/usr/bin/env python3
"""Main entry point for FinCode CLI."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from components.cli import FinCodeCLI


async def main():
    """Main entry point."""
    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Get model and provider from environment or use defaults
    model = os.getenv("MODEL", "grok-3")
    provider = os.getenv("MODEL_PROVIDER", "xai")

    # Create and run app
    cli = FinCodeCLI(model=model, provider=provider)
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
