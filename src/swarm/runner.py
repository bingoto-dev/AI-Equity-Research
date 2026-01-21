"""Swarm runner: planner -> workers -> judge."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from config.settings import Settings
from src.swarm.judge import finalize_task
from src.swarm.planner import plan_tasks
from src.swarm.state import SwarmStateStore
from src.swarm.worker import run_task

logger = logging.getLogger(__name__)


class SwarmRunner:
    """Run a single swarm cycle."""

    def __init__(self, settings: Settings, state_path: Optional[Path] = None):
        self.settings = settings
        self.state_path = state_path or Path("data/swarm/state.json")
        self.store = SwarmStateStore(self.state_path)

    async def run_cycle(self) -> None:
        state = self.store.load()
        config = {
            "hub_interval_minutes": self.settings.swarm.hub_interval_minutes,
            "validate_interval_minutes": self.settings.swarm.validate_interval_minutes,
            "export_interval_minutes": self.settings.swarm.export_interval_minutes,
        }
        state = plan_tasks(state, config)
        now = datetime.utcnow()

        for task in state.tasks:
            if not task.due(now):
                continue
            if task.status == "in_progress":
                continue

            logger.info("Running swarm task: %s", task.task_id)
            task.status = "in_progress"
            ok = False
            message = ""
            try:
                ok, message = await run_task(task, self.settings)
            except Exception as exc:
                ok = False
                message = str(exc)
            finalize_task(task, ok, message)

        self.store.save(state)
        logger.info("Swarm cycle completed")

    async def run_loop(self) -> None:
        while True:
            await self.run_cycle()
            await asyncio.sleep(self.settings.swarm.loop_interval_seconds)
