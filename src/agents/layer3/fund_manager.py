"""Fund Manager Agent - Portfolio Construction Specialist."""

from typing import Any, Dict, Optional

from src.agents.base import AgentOutput, FundManagerAgent, StockPick
from src.llm.client import AgentLLMClient


class FundManagerAgentImpl(FundManagerAgent):
    """Fund Manager implementation for synthesizing Layer 2 outputs."""

    def __init__(
        self,
        system_prompt: str,
        llm_client: Optional[AgentLLMClient] = None,
    ):
        """Initialize Fund Manager agent.

        Args:
            system_prompt: System prompt for the LLM
            llm_client: Optional LLM client (injected)
        """
        super().__init__(system_prompt=system_prompt)
        self.llm_client = llm_client

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
        """Synthesize Layer 2 outputs into final Top 3.

        Args:
            data: Layer 2 outputs and market data
            context: Optional context (e.g., portfolio constraints)

        Returns:
            AgentOutput with top 3 final picks
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not set. Call set_llm_client first.")

        # Get Layer 2 outputs
        layer2_outputs = data.get("layer2_outputs", [])

        # Convert to format expected by LLM client
        layer2_data = [
            {
                "agent_id": output.get("agent_id"),
                "agent_name": output.get("agent_name"),
                "picks": [pick if isinstance(pick, dict) else pick.model_dump()
                         for pick in output.get("picks", [])],
                "reasoning": output.get("reasoning", ""),
            }
            for output in layer2_outputs
        ]

        # Get synthesis from LLM
        picks_data, response = await self.llm_client.synthesize_picks(
            system_prompt=self.system_prompt,
            layer2_outputs=layer2_data,
        )

        # Convert to StockPick objects
        picks = []
        for i, pick in enumerate(picks_data[:3]):  # Ensure only top 3
            stock_pick = StockPick(**pick)
            picks.append(stock_pick)

        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.name,
            layer=self.layer,
            picks=picks,
            reasoning=self._build_synthesis_reasoning(layer2_outputs, picks),
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "model": response.model,
                "layer2_agents": [o.get("agent_name") for o in layer2_outputs],
            },
        )

    def _build_synthesis_reasoning(
        self,
        layer2_outputs: list[dict[str, Any]],
        final_picks: list[StockPick],
    ) -> str:
        """Build synthesis reasoning summary.

        Args:
            layer2_outputs: Original Layer 2 outputs
            final_picks: Final selected picks

        Returns:
            Reasoning string
        """
        lines = [
            "## Synthesis Rationale",
            "",
            "### Input Summary",
        ]

        for output in layer2_outputs:
            agent = output.get("agent_name", "Unknown")
            picks = output.get("picks", [])
            tickers = [p.get("ticker", "") if isinstance(p, dict) else p.ticker for p in picks]
            lines.append(f"- {agent}: {', '.join(tickers)}")

        lines.extend([
            "",
            "### Final Top 3",
        ])

        for i, pick in enumerate(final_picks, 1):
            lines.append(f"{i}. {pick.ticker} (Conviction: {pick.conviction_score})")

        return "\n".join(lines)

    async def get_portfolio_weights(
        self,
        picks: list[StockPick],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> dict[str, float]:
        """Calculate portfolio weights for picks.

        Args:
            picks: List of stock picks
            constraints: Optional portfolio constraints

        Returns:
            Dict mapping ticker to weight (0-1)
        """
        if not picks:
            return {}

        # Simple conviction-weighted allocation
        total_conviction = sum(p.conviction_score for p in picks)

        if total_conviction == 0:
            # Equal weight if no conviction scores
            weight = 1.0 / len(picks)
            return {p.ticker: weight for p in picks}

        weights = {}
        for pick in picks:
            raw_weight = pick.conviction_score / total_conviction

            # Apply constraints if provided
            if constraints:
                max_position = constraints.get("max_position", 0.5)
                min_position = constraints.get("min_position", 0.05)
                raw_weight = max(min_position, min(max_position, raw_weight))

            weights[pick.ticker] = raw_weight

        # Normalize to sum to 1
        total = sum(weights.values())
        return {ticker: w / total for ticker, w in weights.items()}

    def score_diversification(self, picks: list[StockPick]) -> float:
        """Score portfolio diversification.

        Args:
            picks: List of stock picks

        Returns:
            Diversification score 0-1
        """
        if len(picks) <= 1:
            return 0.0

        # Simple sector-based diversification
        # In real implementation, would use correlation matrix
        unique_themes = set()
        for pick in picks:
            # Extract theme from thesis keywords
            thesis_lower = pick.thesis.lower()
            if "hardware" in thesis_lower or "chip" in thesis_lower:
                unique_themes.add("hardware")
            elif "software" in thesis_lower or "cloud" in thesis_lower:
                unique_themes.add("software")
            elif "application" in thesis_lower or "consumer" in thesis_lower:
                unique_themes.add("applications")
            else:
                unique_themes.add("other")

        # Score based on unique themes vs picks
        return min(1.0, len(unique_themes) / len(picks))
