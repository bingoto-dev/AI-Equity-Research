"""CEO Agent - Strategic Oversight & Stability."""

from typing import Any, Dict, List, Optional

from src.agents.base import (
    AgentOutput,
    CEOAgent,
    CEODecision,
    CEOOutput,
    StockPick,
)
from src.llm.client import AgentLLMClient


class CEOAgentImpl(CEOAgent):
    """CEO implementation for KEEP/SWAP decisions and stability oversight."""

    def __init__(
        self,
        system_prompt: str,
        llm_client: Optional[AgentLLMClient] = None,
    ):
        """Initialize CEO agent.

        Args:
            system_prompt: System prompt for the LLM
            llm_client: Optional LLM client (injected)
        """
        super().__init__(system_prompt=system_prompt)
        self.llm_client = llm_client
        self._decision_history: list[CEOOutput] = []

    def set_llm_client(self, client: AgentLLMClient) -> None:
        """Set the LLM client.

        Args:
            client: LLM client to use
        """
        self.llm_client = client

    async def analyze(
        self,
        data: dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentOutput:
        """Analyze is not used for CEO - use review() instead."""
        raise NotImplementedError("CEO uses review() method, not analyze()")

    async def review(
        self,
        previous_top3: Optional[List[StockPick]],
        proposed_top3: list[StockPick],
        loop_number: int,
    ) -> CEOOutput:
        """Review and make KEEP/SWAP decisions.

        Args:
            previous_top3: Previous loop's Top 3 (None for loop 1)
            proposed_top3: New proposed Top 3 from Fund Manager
            loop_number: Current loop iteration number

        Returns:
            CEOOutput with decisions and final Top 3
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not set. Call set_llm_client first.")

        # First loop: just accept the picks
        if loop_number == 1 or not previous_top3:
            decisions = []
            for i, pick in enumerate(proposed_top3[:3], 1):
                decisions.append(
                    CEODecision(
                        position=i,
                        previous_pick=None,
                        proposed_pick=pick,
                        decision="SWAP",  # First loop is always "new"
                        rationale="First loop - establishing baseline positions.",
                        final_pick=pick,
                    )
                )

            output = CEOOutput(
                decisions=decisions,
                final_top3=proposed_top3[:3],
                stability_score=0.0,  # First loop has no stability
                loop_number=loop_number,
            )
            self._decision_history.append(output)
            return output

        # Subsequent loops: make KEEP/SWAP decisions
        previous_data = [p.model_dump() for p in previous_top3]
        proposed_data = [p.model_dump() for p in proposed_top3]

        decisions_data, response = await self.llm_client.get_ceo_decisions(
            system_prompt=self.system_prompt,
            previous_picks=previous_data,
            proposed_picks=proposed_data,
            loop_number=loop_number,
        )

        # Build decisions with proper StockPick objects
        decisions = []
        final_picks = []

        for i, dec_data in enumerate(decisions_data[:3]):
            position = dec_data.get("position", i + 1)
            decision = dec_data.get("decision", "KEEP")

            # Get the appropriate picks
            prev_pick = previous_top3[i] if i < len(previous_top3) else None
            prop_pick = proposed_top3[i] if i < len(proposed_top3) else None

            if decision == "KEEP" and prev_pick:
                final_pick = prev_pick
            elif prop_pick:
                final_pick = prop_pick
            else:
                final_pick = prev_pick or prop_pick

            decisions.append(
                CEODecision(
                    position=position,
                    previous_pick=prev_pick,
                    proposed_pick=prop_pick,
                    decision=decision,
                    rationale=dec_data.get("rationale", ""),
                    final_pick=final_pick,
                )
            )
            final_picks.append(final_pick)

        # Calculate stability score
        stability_score = self._calculate_stability(decisions)

        output = CEOOutput(
            decisions=decisions,
            final_top3=final_picks,
            stability_score=stability_score,
            loop_number=loop_number,
        )
        self._decision_history.append(output)

        return output

    def _calculate_stability(self, decisions: list[CEODecision]) -> float:
        """Calculate stability score based on decisions.

        Args:
            decisions: List of KEEP/SWAP decisions

        Returns:
            Stability score 0-1 (1 = all KEEP)
        """
        if not decisions:
            return 0.0

        keep_count = sum(1 for d in decisions if d.decision == "KEEP")
        return keep_count / len(decisions)

    def get_decision_history(self) -> list[CEOOutput]:
        """Get history of all CEO decisions.

        Returns:
            List of all CEO outputs
        """
        return self._decision_history.copy()

    def get_stability_trend(self) -> list[float]:
        """Get trend of stability scores across loops.

        Returns:
            List of stability scores by loop
        """
        return [output.stability_score for output in self._decision_history]

    def check_convergence(
        self,
        perfect_match_threshold: int = 2,
        set_stability_threshold: int = 3,
    ) -> dict[str, Any]:
        """Check if picks have converged.

        Args:
            perfect_match_threshold: Loops needed for perfect match
            set_stability_threshold: Loops needed for set stability

        Returns:
            Dict with convergence status and reason
        """
        if len(self._decision_history) < 2:
            return {"converged": False, "reason": "Not enough loops"}

        # Get recent Top 3 sets
        recent_sets = []
        for output in self._decision_history[-set_stability_threshold:]:
            tickers = tuple(sorted(p.ticker for p in output.final_top3))
            recent_sets.append(tickers)

        # Check perfect match (same tickers, same order)
        recent_ordered = []
        for output in self._decision_history[-perfect_match_threshold:]:
            ordered = tuple(p.ticker for p in output.final_top3)
            recent_ordered.append(ordered)

        if len(recent_ordered) >= perfect_match_threshold:
            if len(set(recent_ordered)) == 1:
                return {
                    "converged": True,
                    "reason": "perfect_match",
                    "tickers": list(recent_ordered[0]),
                }

        # Check set stability (same tickers, any order)
        if len(recent_sets) >= set_stability_threshold:
            if len(set(recent_sets)) == 1:
                return {
                    "converged": True,
                    "reason": "set_stability",
                    "tickers": list(recent_sets[0]),
                }

        # Check score convergence
        if len(self._decision_history) >= 2:
            last = self._decision_history[-1]
            prev = self._decision_history[-2]

            max_delta = 0
            for i, pick in enumerate(last.final_top3):
                if i < len(prev.final_top3):
                    delta = abs(pick.conviction_score - prev.final_top3[i].conviction_score)
                    max_delta = max(max_delta, delta)

            if max_delta < 5:  # Less than 5% change
                return {
                    "converged": True,
                    "reason": "score_convergence",
                    "max_delta": max_delta,
                }

        return {"converged": False, "reason": "not_converged"}

    def reset(self) -> None:
        """Reset decision history for new research run."""
        self._decision_history.clear()
