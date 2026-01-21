#!/usr/bin/env python3
"""Run the swarm loop continuously."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from src.swarm.runner import SwarmRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    settings = get_settings()
    runner = SwarmRunner(settings)
    asyncio.run(runner.run_loop())


if __name__ == "__main__":
    main()
