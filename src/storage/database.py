"""SQLite database operations for research history."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite


class ResearchDatabase:
    """Async SQLite database for storing research history."""

    SCHEMA = """
    -- Research runs table
    CREATE TABLE IF NOT EXISTS research_runs (
        run_id TEXT PRIMARY KEY,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'running',
        total_loops INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        total_duration_seconds REAL DEFAULT 0,
        convergence_reason TEXT,
        convergence_details TEXT,
        final_picks TEXT,
        metadata TEXT
    );

    -- Loop iterations table
    CREATE TABLE IF NOT EXISTS loop_iterations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        loop_number INTEGER NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        layer1_picks TEXT,
        layer2_picks TEXT,
        proposed_top3 TEXT,
        final_top3 TEXT,
        ceo_decisions TEXT,
        stability_score REAL,
        duration_seconds REAL,
        token_usage TEXT,
        FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
    );

    -- Final picks table (denormalized for quick queries)
    CREATE TABLE IF NOT EXISTS final_picks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        rank INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        company_name TEXT,
        conviction_score REAL,
        thesis TEXT,
        key_risks TEXT,
        catalysts TEXT,
        position_size_pct REAL,
        timestamp TIMESTAMP NOT NULL,
        FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_runs_status ON research_runs(status);
    CREATE INDEX IF NOT EXISTS idx_runs_started ON research_runs(started_at);
    CREATE INDEX IF NOT EXISTS idx_iterations_run ON loop_iterations(run_id);
    CREATE INDEX IF NOT EXISTS idx_picks_ticker ON final_picks(ticker);
    CREATE INDEX IF NOT EXISTS idx_picks_run ON final_picks(run_id);
    """

    def __init__(self, db_path: Path):
        """Initialize the database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database and create schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(str(self.db_path))
        await self._connection.executescript(self.SCHEMA)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def save_run(self, run_data: dict[str, Any]) -> None:
        """Save or update a research run.

        Args:
            run_data: Research run data dict
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO research_runs (
                run_id, started_at, completed_at, status,
                total_loops, total_tokens, total_duration_seconds,
                convergence_reason, convergence_details, final_picks, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_data["run_id"],
                run_data.get("started_at"),
                run_data.get("completed_at"),
                run_data.get("status", "running"),
                len(run_data.get("iterations", [])),
                run_data.get("total_tokens", 0),
                run_data.get("total_duration_seconds", 0),
                run_data.get("convergence_result", {}).get("reason"),
                json.dumps(run_data.get("convergence_result", {})),
                json.dumps(run_data.get("final_picks", [])),
                json.dumps(run_data.get("metadata", {})),
            ),
        )
        await self._connection.commit()

    async def save_iteration(self, run_id: str, iteration: dict[str, Any]) -> None:
        """Save a loop iteration.

        Args:
            run_id: Research run ID
            iteration: Iteration data dict
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        await self._connection.execute(
            """
            INSERT INTO loop_iterations (
                run_id, loop_number, timestamp,
                layer1_picks, layer2_picks, proposed_top3, final_top3,
                ceo_decisions, stability_score, duration_seconds, token_usage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                iteration["loop_number"],
                iteration.get("timestamp", datetime.utcnow().isoformat()),
                json.dumps(iteration.get("layer1_picks", {})),
                json.dumps(iteration.get("layer2_picks", {})),
                json.dumps(iteration.get("proposed_top3", [])),
                json.dumps(iteration.get("final_top3", [])),
                json.dumps(iteration.get("ceo_decisions", [])),
                iteration.get("stability_score", 0),
                iteration.get("duration_seconds", 0),
                json.dumps(iteration.get("token_usage", {})),
            ),
        )
        await self._connection.commit()

    async def save_final_picks(
        self,
        run_id: str,
        picks: list[dict[str, Any]],
        timestamp: datetime,
    ) -> None:
        """Save final picks for a run.

        Args:
            run_id: Research run ID
            picks: List of final picks
            timestamp: Timestamp of the picks
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        for rank, pick in enumerate(picks, 1):
            await self._connection.execute(
                """
                INSERT INTO final_picks (
                    run_id, rank, ticker, company_name,
                    conviction_score, thesis, key_risks, catalysts,
                    position_size_pct, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    rank,
                    pick.get("ticker"),
                    pick.get("company_name"),
                    pick.get("conviction_score"),
                    pick.get("thesis"),
                    json.dumps(pick.get("key_risks", [])),
                    json.dumps(pick.get("catalysts", [])),
                    pick.get("position_size_pct"),
                    timestamp.isoformat(),
                ),
            )
        await self._connection.commit()

    async def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        """Get a research run by ID.

        Args:
            run_id: Research run ID

        Returns:
            Run data dict or None
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        async with self._connection.execute(
            "SELECT * FROM research_runs WHERE run_id = ?",
            (run_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            run = dict(zip(columns, row))

            # Parse JSON fields
            if run.get("convergence_details"):
                run["convergence_details"] = json.loads(run["convergence_details"])
            if run.get("final_picks"):
                run["final_picks"] = json.loads(run["final_picks"])
            if run.get("metadata"):
                run["metadata"] = json.loads(run["metadata"])

            return run

    async def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent research runs.

        Args:
            limit: Maximum number of runs

        Returns:
            List of run data dicts
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        runs = []
        async with self._connection.execute(
            """
            SELECT * FROM research_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            columns = [desc[0] for desc in cursor.description]
            async for row in cursor:
                run = dict(zip(columns, row))
                if run.get("final_picks"):
                    run["final_picks"] = json.loads(run["final_picks"])
                runs.append(run)

        return runs

    async def get_iterations(self, run_id: str) -> list[dict[str, Any]]:
        """Get iterations for a run.

        Args:
            run_id: Research run ID

        Returns:
            List of iteration dicts
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        iterations = []
        async with self._connection.execute(
            """
            SELECT * FROM loop_iterations
            WHERE run_id = ?
            ORDER BY loop_number
            """,
            (run_id,),
        ) as cursor:
            columns = [desc[0] for desc in cursor.description]
            async for row in cursor:
                iteration = dict(zip(columns, row))
                # Parse JSON fields
                for field in ["layer1_picks", "layer2_picks", "proposed_top3",
                             "final_top3", "ceo_decisions", "token_usage"]:
                    if iteration.get(field):
                        iteration[field] = json.loads(iteration[field])
                iterations.append(iteration)

        return iterations

    async def get_ticker_history(
        self,
        ticker: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get history of a ticker in final picks.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of records

        Returns:
            List of pick records for the ticker
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        records = []
        async with self._connection.execute(
            """
            SELECT fp.*, rr.started_at as run_started
            FROM final_picks fp
            JOIN research_runs rr ON fp.run_id = rr.run_id
            WHERE fp.ticker = ?
            ORDER BY fp.timestamp DESC
            LIMIT ?
            """,
            (ticker, limit),
        ) as cursor:
            columns = [desc[0] for desc in cursor.description]
            async for row in cursor:
                record = dict(zip(columns, row))
                if record.get("key_risks"):
                    record["key_risks"] = json.loads(record["key_risks"])
                if record.get("catalysts"):
                    record["catalysts"] = json.loads(record["catalysts"])
                records.append(record)

        return records

    async def get_statistics(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Statistics dict
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        stats = {}

        # Total runs
        async with self._connection.execute(
            "SELECT COUNT(*) FROM research_runs"
        ) as cursor:
            row = await cursor.fetchone()
            stats["total_runs"] = row[0]

        # Runs by status
        async with self._connection.execute(
            "SELECT status, COUNT(*) FROM research_runs GROUP BY status"
        ) as cursor:
            stats["runs_by_status"] = dict(await cursor.fetchall())

        # Average loops per run
        async with self._connection.execute(
            "SELECT AVG(total_loops) FROM research_runs WHERE status = 'completed'"
        ) as cursor:
            row = await cursor.fetchone()
            stats["avg_loops"] = row[0] or 0

        # Top picked tickers
        async with self._connection.execute(
            """
            SELECT ticker, COUNT(*) as count, AVG(conviction_score) as avg_conviction
            FROM final_picks
            GROUP BY ticker
            ORDER BY count DESC
            LIMIT 10
            """
        ) as cursor:
            stats["top_tickers"] = [
                {"ticker": row[0], "count": row[1], "avg_conviction": row[2]}
                async for row in cursor
            ]

        # Total tokens used
        async with self._connection.execute(
            "SELECT SUM(total_tokens) FROM research_runs"
        ) as cursor:
            row = await cursor.fetchone()
            stats["total_tokens"] = row[0] or 0

        return stats
