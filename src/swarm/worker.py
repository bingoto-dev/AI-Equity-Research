"""Task execution for swarm tasks."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Tuple

from config.settings import Settings
from scripts.build_hub import build_hub
from src.hub.runner import run_daily_landscape
from src.swarm.state import SwarmTask


def _run_subprocess(command: list[str]) -> Tuple[bool, str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stderr.strip() or result.stdout.strip()


async def run_task(task: SwarmTask, settings: Settings) -> Tuple[bool, str]:
    if task.task_type == "hub_pipeline":
        outputs = await run_daily_landscape(
            mappings_path=settings.hub.mappings_path,
            output_dir=settings.hub.output_dir,
            templates_dir=settings.templates_dir,
            top_themes=settings.hub.top_themes,
            top_companies=settings.hub.top_companies,
            include_memos=settings.hub.include_memos,
        )

        if settings.hub.build_static:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            build_hub(
                report_date=date_str,
                reports_dir=settings.hub.output_dir,
                templates_dir=settings.templates_dir,
                output_dir=settings.hub.hub_output_dir,
            )
        return True, str(outputs)

    if task.task_type == "validate_mappings":
        ok, output = _run_subprocess([
            "python3",
            "scripts/validate_ontology_mappings.py",
            str(settings.hub.mappings_path),
        ])
        return ok, output

    if task.task_type == "export_mappings":
        ok, output = _run_subprocess([
            "python3",
            "scripts/export_ontology_mappings_csv.py",
            str(settings.hub.mappings_path),
            "docs/spec/mappings",
        ])
        return ok, output

    return False, f"Unknown task type: {task.task_type}"
