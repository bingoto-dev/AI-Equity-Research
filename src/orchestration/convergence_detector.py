"""Convergence detection for the research loop."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.agents.base import StockPick


class ConvergenceReason(Enum):
    """Reasons for convergence."""

    NOT_CONVERGED = "not_converged"
    PERFECT_MATCH = "perfect_match"
    SET_STABILITY = "set_stability"
    SCORE_CONVERGENCE = "score_convergence"
    MAX_LOOPS = "max_loops"


@dataclass
class ConvergenceResult:
    """Result of convergence check."""

    converged: bool
    reason: ConvergenceReason
    details: dict[str, Any]
    loop_number: int


class ConvergenceDetector:
    """Detects when the research loop has converged."""

    def __init__(
        self,
        perfect_match_loops: int = 2,
        set_stability_loops: int = 3,
        score_threshold: float = 0.05,
        max_loops: int = 5,
    ):
        """Initialize the convergence detector.

        Args:
            perfect_match_loops: Consecutive loops for perfect match
            set_stability_loops: Consecutive loops for set stability
            score_threshold: Max score change % for score convergence
            max_loops: Maximum loops before forced convergence
        """
        self.perfect_match_loops = perfect_match_loops
        self.set_stability_loops = set_stability_loops
        self.score_threshold = score_threshold
        self.max_loops = max_loops

        self._history: list[list[StockPick]] = []
        self._score_history: list[list[float]] = []

    def add_result(self, top3: list[StockPick]) -> None:
        """Add a loop result to history.

        Args:
            top3: The top 3 picks from this loop
        """
        self._history.append(top3.copy())
        self._score_history.append([p.conviction_score for p in top3])

    def check(self) -> ConvergenceResult:
        """Check if convergence criteria are met.

        Returns:
            ConvergenceResult with status and details
        """
        loop_number = len(self._history)

        # Check max loops first
        if loop_number >= self.max_loops:
            return ConvergenceResult(
                converged=True,
                reason=ConvergenceReason.MAX_LOOPS,
                details={"max_loops": self.max_loops},
                loop_number=loop_number,
            )

        # Need at least 2 loops for any convergence check
        if loop_number < 2:
            return ConvergenceResult(
                converged=False,
                reason=ConvergenceReason.NOT_CONVERGED,
                details={"message": "Not enough loops"},
                loop_number=loop_number,
            )

        # Check perfect match (same tickers in same order)
        if loop_number >= self.perfect_match_loops:
            if self._check_perfect_match():
                tickers = [p.ticker for p in self._history[-1]]
                return ConvergenceResult(
                    converged=True,
                    reason=ConvergenceReason.PERFECT_MATCH,
                    details={
                        "tickers": tickers,
                        "consecutive_matches": self.perfect_match_loops,
                    },
                    loop_number=loop_number,
                )

        # Check set stability (same tickers, any order)
        if loop_number >= self.set_stability_loops:
            if self._check_set_stability():
                tickers = sorted(p.ticker for p in self._history[-1])
                return ConvergenceResult(
                    converged=True,
                    reason=ConvergenceReason.SET_STABILITY,
                    details={
                        "tickers": tickers,
                        "consecutive_stable": self.set_stability_loops,
                    },
                    loop_number=loop_number,
                )

        # Check score convergence
        if self._check_score_convergence():
            max_delta = self._get_max_score_delta()
            return ConvergenceResult(
                converged=True,
                reason=ConvergenceReason.SCORE_CONVERGENCE,
                details={
                    "max_delta": max_delta,
                    "threshold": self.score_threshold,
                },
                loop_number=loop_number,
            )

        return ConvergenceResult(
            converged=False,
            reason=ConvergenceReason.NOT_CONVERGED,
            details=self._get_convergence_progress(),
            loop_number=loop_number,
        )

    def _check_perfect_match(self) -> bool:
        """Check if last N loops have identical picks in order.

        Returns:
            True if perfect match detected
        """
        if len(self._history) < self.perfect_match_loops:
            return False

        recent = self._history[-self.perfect_match_loops:]
        first_tickers = tuple(p.ticker for p in recent[0])

        for picks in recent[1:]:
            if tuple(p.ticker for p in picks) != first_tickers:
                return False

        return True

    def _check_set_stability(self) -> bool:
        """Check if last N loops have same set of tickers.

        Returns:
            True if set stability detected
        """
        if len(self._history) < self.set_stability_loops:
            return False

        recent = self._history[-self.set_stability_loops:]
        first_set = frozenset(p.ticker for p in recent[0])

        for picks in recent[1:]:
            if frozenset(p.ticker for p in picks) != first_set:
                return False

        return True

    def _check_score_convergence(self) -> bool:
        """Check if scores have converged within threshold.

        Returns:
            True if score convergence detected
        """
        if len(self._score_history) < 2:
            return False

        return self._get_max_score_delta() < self.score_threshold * 100

    def _get_max_score_delta(self) -> float:
        """Get maximum score change between last two loops.

        Returns:
            Maximum absolute score delta
        """
        if len(self._score_history) < 2:
            return 100.0

        last = self._score_history[-1]
        prev = self._score_history[-2]

        max_delta = 0.0
        for i in range(min(len(last), len(prev))):
            delta = abs(last[i] - prev[i])
            max_delta = max(max_delta, delta)

        return max_delta

    def _get_convergence_progress(self) -> dict[str, Any]:
        """Get progress towards convergence.

        Returns:
            Dict with progress metrics
        """
        progress = {
            "loops_completed": len(self._history),
            "max_loops": self.max_loops,
        }

        if len(self._history) >= 2:
            # Count consecutive matching sets
            consecutive = 1
            last_set = frozenset(p.ticker for p in self._history[-1])
            for picks in reversed(self._history[:-1]):
                if frozenset(p.ticker for p in picks) == last_set:
                    consecutive += 1
                else:
                    break
            progress["consecutive_set_matches"] = consecutive
            progress["set_stability_needed"] = self.set_stability_loops

            # Count consecutive perfect matches
            consecutive_perfect = 1
            last_ordered = tuple(p.ticker for p in self._history[-1])
            for picks in reversed(self._history[:-1]):
                if tuple(p.ticker for p in picks) == last_ordered:
                    consecutive_perfect += 1
                else:
                    break
            progress["consecutive_perfect_matches"] = consecutive_perfect
            progress["perfect_match_needed"] = self.perfect_match_loops

            # Score delta
            progress["last_score_delta"] = self._get_max_score_delta()
            progress["score_threshold"] = self.score_threshold * 100

        return progress

    def reset(self) -> None:
        """Reset the detector for a new research run."""
        self._history.clear()
        self._score_history.clear()

    def get_history(self) -> list[list[StockPick]]:
        """Get full history of picks.

        Returns:
            List of top 3 picks for each loop
        """
        return [picks.copy() for picks in self._history]

    def get_ticker_frequency(self) -> dict[str, int]:
        """Get frequency of each ticker across all loops.

        Returns:
            Dict mapping ticker to appearance count
        """
        frequency: dict[str, int] = {}
        for picks in self._history:
            for pick in picks:
                frequency[pick.ticker] = frequency.get(pick.ticker, 0) + 1
        return frequency

    def get_stability_trend(self) -> list[float]:
        """Calculate stability trend across loops.

        Returns:
            List of stability scores (0-1) for each loop transition
        """
        if len(self._history) < 2:
            return []

        stability = []
        for i in range(1, len(self._history)):
            prev_set = frozenset(p.ticker for p in self._history[i - 1])
            curr_set = frozenset(p.ticker for p in self._history[i])
            overlap = len(prev_set & curr_set)
            stability.append(overlap / 3)  # 3 picks, so max overlap is 3

        return stability
