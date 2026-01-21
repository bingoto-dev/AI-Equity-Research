"""State persistence manager for research runs."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.orchestration.loop_controller import ResearchRun
from src.storage.database import ResearchDatabase


class StateManager:
    """Manages state persistence for research runs."""

    def __init__(self, database: ResearchDatabase, state_dir: Optional[Path] = None):
        """Initialize the state manager.

        Args:
            database: Research database instance
            state_dir: Optional directory for state files
        """
        self.database = database
        self.state_dir = state_dir or Path("data/state")
        self._current_run_id: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize the state manager."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        await self.database.initialize()

    async def close(self) -> None:
        """Close the state manager."""
        await self.database.close()

    async def start_run(self, run: ResearchRun) -> None:
        """Start tracking a new research run.

        Args:
            run: Research run to track
        """
        self._current_run_id = run.run_id

        # Save initial state to database
        await self.database.save_run({
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "status": "running",
        })

        # Save state file for recovery
        self._save_state_file(run)

    async def update_run(self, run: ResearchRun) -> None:
        """Update a research run.

        Args:
            run: Updated research run
        """
        await self.database.save_run({
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "status": run.status,
            "iterations": [i.model_dump() for i in run.iterations],
            "total_tokens": run.total_tokens,
            "total_duration_seconds": run.total_duration_seconds,
            "convergence_result": run.convergence_result,
            "final_picks": run.final_picks,
        })

        # Update state file
        self._save_state_file(run)

    async def save_iteration(self, run_id: str, iteration: Any) -> None:
        """Save a loop iteration.

        Args:
            run_id: Research run ID
            iteration: Iteration data
        """
        iteration_data = iteration.model_dump() if hasattr(iteration, 'model_dump') else iteration
        await self.database.save_iteration(run_id, iteration_data)

    async def complete_run(self, run: ResearchRun) -> None:
        """Mark a run as complete and save final state.

        Args:
            run: Completed research run
        """
        # Update database
        await self.database.save_run({
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else datetime.utcnow().isoformat(),
            "status": "completed",
            "iterations": [i.model_dump() for i in run.iterations],
            "total_tokens": run.total_tokens,
            "total_duration_seconds": run.total_duration_seconds,
            "convergence_result": run.convergence_result,
            "final_picks": run.final_picks,
        })

        # Save final picks
        if run.final_picks:
            await self.database.save_final_picks(
                run.run_id,
                run.final_picks,
                run.completed_at or datetime.utcnow(),
            )

        # Remove state file (run is complete)
        self._remove_state_file(run.run_id)
        self._current_run_id = None

    async def fail_run(self, run_id: str, error: str) -> None:
        """Mark a run as failed.

        Args:
            run_id: Research run ID
            error: Error message
        """
        run_data = await self.database.get_run(run_id)
        if run_data:
            run_data["status"] = "failed"
            run_data["metadata"] = run_data.get("metadata", {})
            run_data["metadata"]["error"] = error
            run_data["completed_at"] = datetime.utcnow().isoformat()
            await self.database.save_run(run_data)

        self._current_run_id = None

    async def get_incomplete_runs(self) -> list[dict[str, Any]]:
        """Get runs that didn't complete (for recovery).

        Returns:
            List of incomplete run data
        """
        # Check state files
        incomplete = []
        for state_file in self.state_dir.glob("run_*.json"):
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    if state.get("status") == "running":
                        incomplete.append(state)
            except Exception:
                continue

        return incomplete

    async def recover_run(self, run_id: str) -> Optional[ResearchRun]:
        """Attempt to recover a run from state.

        Args:
            run_id: Research run ID

        Returns:
            Recovered ResearchRun or None
        """
        state_file = self.state_dir / f"{run_id}.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file) as f:
                state = json.load(f)

            # Reconstruct ResearchRun
            return ResearchRun(**state)
        except Exception:
            return None

    def _save_state_file(self, run: ResearchRun) -> None:
        """Save run state to file for recovery.

        Args:
            run: Research run to save
        """
        state_file = self.state_dir / f"{run.run_id}.json"
        state = run.model_dump()

        # Convert datetime objects
        if isinstance(state.get("started_at"), datetime):
            state["started_at"] = state["started_at"].isoformat()
        if isinstance(state.get("completed_at"), datetime):
            state["completed_at"] = state["completed_at"].isoformat()

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def _remove_state_file(self, run_id: str) -> None:
        """Remove state file after completion.

        Args:
            run_id: Research run ID
        """
        state_file = self.state_dir / f"{run_id}.json"
        if state_file.exists():
            state_file.unlink()

    async def get_run_history(
        self,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get run history with optional filtering.

        Args:
            limit: Maximum number of runs
            status: Optional status filter

        Returns:
            List of run data dicts
        """
        runs = await self.database.get_recent_runs(limit * 2)  # Get more, then filter

        if status:
            runs = [r for r in runs if r.get("status") == status]

        return runs[:limit]

    async def get_ticker_performance(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        """Get performance history for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Performance data dict
        """
        history = await self.database.get_ticker_history(ticker)

        if not history:
            return {"ticker": ticker, "appearances": 0}

        return {
            "ticker": ticker,
            "appearances": len(history),
            "average_rank": sum(h["rank"] for h in history) / len(history),
            "average_conviction": sum(h["conviction_score"] or 0 for h in history) / len(history),
            "first_appearance": min(h["timestamp"] for h in history),
            "last_appearance": max(h["timestamp"] for h in history),
            "history": history,
        }

    async def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for a dashboard view.

        Returns:
            Dashboard data dict
        """
        stats = await self.database.get_statistics()
        recent = await self.database.get_recent_runs(5)

        return {
            "statistics": stats,
            "recent_runs": recent,
            "current_run_id": self._current_run_id,
        }
