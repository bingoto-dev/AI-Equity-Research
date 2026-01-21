"""Swarm planner for scheduled tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from src.swarm.state import SwarmState, SwarmTask


DEFAULT_TASKS = {
    "hub_pipeline": {"interval_minutes": 1440},
    "validate_mappings": {"interval_minutes": 1440},
    "export_mappings": {"interval_minutes": 1440},
}


def plan_tasks(state: SwarmState, config: Dict[str, object]) -> SwarmState:
    existing = {task.task_id: task for task in state.tasks}

    for task_id, defaults in DEFAULT_TASKS.items():
        if task_id not in existing:
            state.tasks.append(
                SwarmTask(
                    task_id=task_id,
                    task_type=task_id,
                    interval_minutes=defaults.get("interval_minutes", 1440),
                )
            )

    for task in state.tasks:
        if task.task_id == "hub_pipeline":
            task.interval_minutes = int(config.get("hub_interval_minutes", task.interval_minutes))
        elif task.task_id == "validate_mappings":
            task.interval_minutes = int(config.get("validate_interval_minutes", task.interval_minutes))
        elif task.task_id == "export_mappings":
            task.interval_minutes = int(config.get("export_interval_minutes", task.interval_minutes))

    state.last_cycle_at = datetime.utcnow().isoformat()
    return state
