"""Judge decisions for swarm tasks."""

from __future__ import annotations

from datetime import datetime

from src.swarm.state import SwarmTask


def finalize_task(task: SwarmTask, ok: bool, message: str) -> None:
    now = datetime.utcnow()
    if ok:
        task.mark_scheduled(now)
    else:
        task.mark_failed(message)
