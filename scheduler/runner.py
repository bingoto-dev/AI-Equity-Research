"""APScheduler setup for scheduled research runs."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings, Settings
from src.hub.runner import run_daily_landscape
from scripts.build_hub import build_hub
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


class ResearchRunner:
    """Runs scheduled research jobs."""

    def __init__(self, settings: Settings):
        """Initialize the research runner.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._scheduler: Optional[AsyncIOScheduler] = None

        # Initialize components
        self._database = ResearchDatabase(settings.database.path)
        self._state_manager = StateManager(
            self._database,
            Path("data/state"),
        )

        # Initialize data sources
        self._data_registry = create_default_registry(
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
        self._agent_registry = AgentRegistry(settings.prompts_path)

        # Initialize notifiers
        self._email = EmailNotifier(settings.notifications)
        self._slack = SlackNotifier(settings.notifications)
        self._discord = DiscordNotifier(settings.notifications)

        # Initialize report generator
        self._report_generator = ReportGenerator(
            templates_dir=settings.templates_dir,
            output_dir=settings.reports_dir,
        )

    async def initialize(self) -> None:
        """Initialize all components."""
        await self._state_manager.initialize()
        logger.info("Research runner initialized")

    async def shutdown(self) -> None:
        """Shutdown all components."""
        await self._state_manager.close()
        if self._scheduler:
            self._scheduler.shutdown()
        logger.info("Research runner shutdown complete")

    async def run_research(self) -> None:
        """Execute a single research run."""
        logger.info("Starting scheduled research run")

        try:
            # Create loop controller
            controller = LoopController(
                settings=self.settings,
                agent_registry=self._agent_registry,
                data_registry=self._data_registry,
            )

            # Run the research loop
            run = await controller.run()

            # Save to state manager
            await self._state_manager.complete_run(run)

            # Generate report
            report_path = self._report_generator.generate_report(run)
            summary = self._report_generator.generate_summary(run)

            logger.info(f"Research complete: {run.run_id}")
            logger.info(f"Report generated: {report_path}")

            # Send notifications
            await self._send_notifications(run.run_id, summary, run.final_picks, report_path)

        except Exception as e:
            logger.error(f"Research run failed: {e}")
            await self._send_error_notifications(str(e))

    async def run_hub(self) -> None:
        """Execute hub pipeline: landscape + memos + static hub build."""
        if not self.settings.hub.enabled:
            logger.info("Hub pipeline disabled")
            return

        logger.info("Starting hub pipeline run")
        try:
            outputs = await run_daily_landscape(
                mappings_path=self.settings.hub.mappings_path,
                output_dir=self.settings.hub.output_dir,
                templates_dir=self.settings.templates_dir,
                top_themes=self.settings.hub.top_themes,
                top_companies=self.settings.hub.top_companies,
                include_memos=self.settings.hub.include_memos,
            )

            logger.info("Hub pipeline outputs: %s", outputs)

            if self.settings.hub.build_static:
                date_str = datetime.utcnow().strftime("%Y-%m-%d")
                build_hub(
                    report_date=date_str,
                    reports_dir=self.settings.hub.output_dir,
                    templates_dir=self.settings.templates_dir,
                    output_dir=self.settings.hub.hub_output_dir,
                )
                logger.info("Hub UI built")

        except Exception as e:
            logger.error(f"Hub pipeline failed: {e}")
            raise

    async def _send_notifications(
        self,
        run_id: str,
        summary: str,
        picks: list,
        report_path: str,
    ) -> None:
        """Send completion notifications.

        Args:
            run_id: Research run ID
            summary: Summary text
            picks: Final picks
            report_path: Path to report
        """
        tasks = []

        if self._email.is_enabled:
            tasks.append(
                self._email.send_research_complete(run_id, summary, report_path)
            )

        if self._slack.is_enabled:
            tasks.append(
                self._slack.send_research_complete(run_id, summary, picks)
            )

        if self._discord.is_enabled:
            tasks.append(
                self._discord.send_research_complete(run_id, summary, picks)
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_error_notifications(self, error: str) -> None:
        """Send error notifications.

        Args:
            error: Error message
        """
        run_id = f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        tasks = []

        if self._email.is_enabled:
            tasks.append(self._email.send_error(run_id, error))

        if self._slack.is_enabled:
            tasks.append(self._slack.send_error(run_id, error))

        if self._discord.is_enabled:
            tasks.append(self._discord.send_error(run_id, error))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def setup_scheduler(self) -> AsyncIOScheduler:
        """Setup the APScheduler.

        Returns:
            Configured scheduler
        """
        self._scheduler = AsyncIOScheduler(timezone=self.settings.scheduler.timezone)

        # Parse cron expression
        cron_parts = self.settings.scheduler.cron_expression.split()
        trigger = CronTrigger(
            minute=cron_parts[0] if len(cron_parts) > 0 else "*",
            hour=cron_parts[1] if len(cron_parts) > 1 else "*",
            day=cron_parts[2] if len(cron_parts) > 2 else "*",
            month=cron_parts[3] if len(cron_parts) > 3 else "*",
            day_of_week=cron_parts[4] if len(cron_parts) > 4 else "*",
            timezone=self.settings.scheduler.timezone,
        )

        self._scheduler.add_job(
            self.run_research,
            trigger=trigger,
            id="research_job",
            name="AI Equity Research",
            replace_existing=True,
        )

        if self.settings.hub.enabled:
            hub_parts = self.settings.hub.cron_expression.split()
            hub_trigger = CronTrigger(
                minute=hub_parts[0] if len(hub_parts) > 0 else "*",
                hour=hub_parts[1] if len(hub_parts) > 1 else "*",
                day=hub_parts[2] if len(hub_parts) > 2 else "*",
                month=hub_parts[3] if len(hub_parts) > 3 else "*",
                day_of_week=hub_parts[4] if len(hub_parts) > 4 else "*",
                timezone=self.settings.scheduler.timezone,
            )

            self._scheduler.add_job(
                self.run_hub,
                trigger=hub_trigger,
                id="hub_job",
                name="Hub Pipeline",
                replace_existing=True,
            )

            logger.info(
                f"Scheduled hub job: {self.settings.hub.cron_expression} "
                f"({self.settings.scheduler.timezone})"
            )

        logger.info(
            f"Scheduled research job: {self.settings.scheduler.cron_expression} "
            f"({self.settings.scheduler.timezone})"
        )

        return self._scheduler

    def start(self) -> None:
        """Start the scheduler."""
        if not self._scheduler:
            self.setup_scheduler()
        self._scheduler.start()
        logger.info("Scheduler started")


async def main():
    """Main entry point for scheduled runner."""
    settings = get_settings()
    runner = ResearchRunner(settings)

    await runner.initialize()
    runner.start()

    logger.info("Research scheduler running. Press Ctrl+C to exit.")

    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
