#!/usr/bin/env python3
"""Run full hub pipeline: landscape + memos + static hub build."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from scripts.build_hub import build_hub
from src.hub.runner import run_daily_landscape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main_async(top_themes: Optional[int], top_companies: Optional[int], include_memos: bool) -> int:
    settings = get_settings()
    logger.info("Running hub pipeline")

    outputs = await run_daily_landscape(
        mappings_path=settings.hub.mappings_path,
        output_dir=settings.hub.output_dir,
        templates_dir=settings.templates_dir,
        top_themes=top_themes or settings.hub.top_themes,
        top_companies=top_companies or settings.hub.top_companies,
        include_memos=include_memos,
    )

    logger.info("Hub pipeline outputs: %s", outputs)

    if settings.hub.build_static:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        build_hub(
            report_date=date_str,
            reports_dir=settings.hub.output_dir,
            templates_dir=settings.templates_dir,
            output_dir=settings.hub.hub_output_dir,
        )
        logger.info("Hub UI built")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full hub pipeline")
    parser.add_argument("--top-themes", type=int, default=None, help="Top themes to memo")
    parser.add_argument("--top-companies", type=int, default=None, help="Top companies to rank")
    parser.add_argument("--skip-memos", action="store_true", help="Skip memo generation")

    args = parser.parse_args()
    exit_code = asyncio.run(
        main_async(
            top_themes=args.top_themes,
            top_companies=args.top_companies,
            include_memos=not args.skip_memos,
        )
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
