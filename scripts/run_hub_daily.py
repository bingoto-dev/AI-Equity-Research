#!/usr/bin/env python3
"""Generate daily landscape brief and theme memos."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hub.runner import run_daily_landscape_cli

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily landscape and memo pipeline")
    parser.add_argument(
        "--mappings",
        default="docs/spec/ONTOLOGY_MAPPINGS.json",
        help="Path to ontology mappings JSON",
    )
    parser.add_argument(
        "--output-dir",
        default="data/reports",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--templates-dir",
        default="src/reports/templates",
        help="Templates directory",
    )
    parser.add_argument("--top-themes", type=int, default=5, help="Top themes to memo")
    parser.add_argument("--top-companies", type=int, default=10, help="Top companies to rank")
    parser.add_argument(
        "--skip-memos",
        action="store_true",
        help="Skip memo generation",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(
        run_daily_landscape_cli(
            mappings_path=Path(args.mappings),
            output_dir=Path(args.output_dir),
            templates_dir=Path(args.templates_dir),
            top_themes=args.top_themes,
            top_companies=args.top_companies,
            include_memos=not args.skip_memos,
        )
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
