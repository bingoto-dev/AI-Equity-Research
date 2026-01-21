"""Persistent swarm state storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SwarmTask:
    task_id: str
    task_type: str
    status: str = "idle"  # idle, in_progress, success, failed
    interval_minutes: int = 1440
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None
    payload: Dict[str, object] = field(default_factory=dict)

    def due(self, now: datetime) -> bool:
        if not self.next_run_at:
            return True
        try:
            next_dt = datetime.fromisoformat(self.next_run_at)
        except ValueError:
            return True
        return now >= next_dt

    def mark_scheduled(self, now: datetime) -> None:
        self.last_run_at = now.isoformat()
        self.next_run_at = (now + self._interval()).isoformat()
        self.status = "success"
        self.attempts = 0
        self.last_error = None

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.attempts += 1
        self.last_error = error

    def _interval(self):
        from datetime import timedelta
        return timedelta(minutes=self.interval_minutes)


@dataclass
class SwarmState:
    tasks: List[SwarmTask] = field(default_factory=list)
    last_cycle_at: Optional[str] = None

    def to_json(self) -> Dict[str, object]:
        return {
            "tasks": [asdict(task) for task in self.tasks],
            "last_cycle_at": self.last_cycle_at,
        }

    @classmethod
    def from_json(cls, data: Dict[str, object]) -> "SwarmState":
        tasks = []
        for item in data.get("tasks", []):
            tasks.append(SwarmTask(**item))
        return cls(tasks=tasks, last_cycle_at=data.get("last_cycle_at"))


class SwarmStateStore:
    """JSON file-based state store."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> SwarmState:
        if not self.path.exists():
            return SwarmState()
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return SwarmState.from_json(data)

    def save(self, state: SwarmState) -> None:
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(state.to_json(), handle, indent=2)
