#!/usr/bin/env python3
"""Manual single execution of AI research."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from src.agents.registry import AgentRegistry
from src.data_sources.registry import create_default_registry
from src.notifications.discord_notifier import DiscordNotifier
from src.notifications.email_notifier import EmailNotifier
from src.notifications.slack_notifier import SlackNotifier
from src.orchestration.loop_controller import LoopController
from src.reports.generator import ReportGenerator
from src.storage.database import ResearchDatabase
from src.storage.state_manager import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_once(
    skip_notifications: bool = False,
    verbose: bool = False,
) -> int:
    """Run a single research analysis.

    Args:
        skip_notifications: Skip sending notifications
        verbose: Enable verbose logging

    Returns:
        Exit code (0 for success)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    settings = get_settings()

    logger.info("=" * 60)
    logger.info("AI Equity Research - Single Run")
    logger.info("=" * 60)

    # Initialize database
    database = ResearchDatabase(settings.database.path)
    state_manager = StateManager(database, Path("data/state"))
    await state_manager.initialize()

    # Initialize data sources
    logger.info("Initializing data sources...")
    data_registry = create_default_registry(
        news_api_key=(
            settings.data_sources.news_api_key.get_secret_value()
            if settings.data_sources.news_api_key
            else None
        ),
        alpha_vantage_key=(
            settings.data_sources.alpha_vantage_key.get_secret_value()
            if settings.data_sources.alpha_vantage_key
            else None
        ),
        sec_user_agent=settings.data_sources.sec_user_agent,
        fred_api_key=(
            settings.data_sources.fred_api_key.get_secret_value()
            if settings.data_sources.fred_api_key
            else None
        ),
        github_token=(
            settings.data_sources.github_token.get_secret_value()
            if settings.data_sources.github_token
            else None
        ),
    )

    # Initialize agent registry
    agent_registry = AgentRegistry(settings.prompts_path)

    # Initialize report generator
    report_generator = ReportGenerator(
        templates_dir=settings.templates_dir,
        output_dir=settings.reports_dir,
    )

    try:
        # Create and run loop controller
        logger.info("Starting research loop...")
        controller = LoopController(
            settings=settings,
            agent_registry=agent_registry,
            data_registry=data_registry,
        )

        run = await controller.run()

        # Save to state manager
        await state_manager.complete_run(run)

        # Generate report
        logger.info("Generating report...")
        report_path = report_generator.generate_report(run)
        summary = report_generator.generate_summary(run)

        # Print results
        logger.info("=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        logger.info(f"Run ID: {run.run_id}")
        logger.info(f"Status: {run.status}")
        logger.info(f"Loops: {len(run.iterations)}")
        logger.info(f"Convergence: {run.convergence_result.get('reason', 'N/A')}")
        logger.info(f"Duration: {run.total_duration_seconds:.1f}s")
        logger.info(f"Tokens: {run.total_tokens}")
        logger.info("")
        logger.info("TOP 3 PICKS:")
        for i, pick in enumerate(run.final_picks[:3], 1):
            ticker = pick.get("ticker", "N/A")
            company = pick.get("company_name", "Unknown")
            conviction = pick.get("conviction_score", 0)
            logger.info(f"  {i}. {ticker} - {company} ({conviction:.0f}%)")
        logger.info("")
        logger.info(f"Report saved: {report_path}")

        # Send notifications if not skipped
        if not skip_notifications:
            logger.info("Sending notifications...")
            await _send_notifications(
                settings,
                run.run_id,
                summary,
                run.final_picks,
                report_path,
            )

        return 0

    except Exception as e:
        logger.error(f"Research failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await state_manager.close()


async def _send_notifications(
    settings,
    run_id: str,
    summary: str,
    picks: list,
    report_path: str,
) -> None:
    """Send notifications."""
    tasks = []

    email = EmailNotifier(settings.notifications)
    if email.is_enabled:
        tasks.append(email.send_research_complete(run_id, summary, report_path))

    slack = SlackNotifier(settings.notifications)
    if slack.is_enabled:
        tasks.append(slack.send_research_complete(run_id, summary, picks))

    discord = DiscordNotifier(settings.notifications)
    if discord.is_enabled:
        tasks.append(discord.send_research_complete(run_id, summary, picks))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Notification failed: {r}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run AI Equity Research analysis"
    )
    parser.add_argument(
        "--skip-notifications",
        action="store_true",
        help="Skip sending notifications",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(
        run_once(
            skip_notifications=args.skip_notifications,
            verbose=args.verbose,
        )
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
