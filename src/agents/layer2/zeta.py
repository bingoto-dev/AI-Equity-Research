"""Zeta Agent - Risk & Contrarian Analysis Specialist."""

from typing import Any, Dict, Optional

from src.agents.base import AgentOutput, Layer2Agent, StockPick
from src.llm.client import AgentLLMClient


class ZetaAgent(Layer2Agent):
    """Zeta agent specializing in risk assessment and contrarian views."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        specialties: list[str],
        llm_client: Optional[AgentLLMClient] = None,
    ):
        """Initialize Zeta agent.

        Args:
            name: Agent display name
            system_prompt: System prompt for the LLM
            specialties: List of analytical specialties
            llm_client: Optional LLM client (injected)
        """
        super().__init__(
            agent_id="zeta",
            name=name,
            system_prompt=system_prompt,
            specialties=specialties,
        )
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
        """Perform risk and contrarian analysis on candidate companies.

        Args:
            data: Market data including Layer 1 outputs
            context: Optional context

        Returns:
            AgentOutput with top 5 risk-adjusted picks
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not set. Call set_llm_client first.")

        # Build data summary
        data_summary = self._build_data_summary(data, context)

        # Get picks from LLM
        picks_data, response = await self.llm_client.get_top_picks(
            system_prompt=self.system_prompt,
            data_summary=data_summary,
            num_picks=5,
        )

        # Convert to StockPick objects and add risk scores
        picks = []
        for pick in picks_data:
            stock_pick = StockPick(**pick)
            # Add risk-specific scoring and position sizing
            stock_pick.risk_score = pick.get("conviction_score", 50)
            stock_pick.position_size_recommendation = pick.get("position_size_recommendation", 2.0)
            stock_pick.bear_case = pick.get("bear_case", "")
            picks.append(stock_pick)

        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.name,
            layer=self.layer,
            picks=picks,
            reasoning="Risk analysis with contrarian perspective and position sizing recommendations.",
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "model": response.model,
                "specialties": self.specialties,
            },
        )

    def _build_data_summary(
        self,
        data: dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Build data summary for LLM consumption.

        Args:
            data: Raw market data including Layer 1 outputs
            context: Optional context

        Returns:
            Formatted data summary string
        """
        lines = [
            "# Risk & Contrarian Analysis - Layer 2",
            "",
            "## Your Role",
            "Stress-test the candidate pool, identify risks, and provide position sizing.",
            "Challenge consensus views and find overlooked opportunities.",
            f"Focus: {', '.join(self.specialties)}",
            "",
        ]

        # Add Layer 1 candidate pool with conviction scores
        layer1_outputs = data.get("layer1_outputs", [])
        if layer1_outputs:
            lines.append("## Candidate Pool from Layer 1 (Assess Crowding Risk)")
            all_tickers = {}
            for output in layer1_outputs:
                for pick in output.get("picks", []):
                    ticker = pick.get("ticker", "")
                    if ticker not in all_tickers:
                        all_tickers[ticker] = []
                    all_tickers[ticker].append({
                        "agent": output.get("agent_name", "Unknown"),
                        "conviction": pick.get("conviction_score", 0),
                    })

            # Show tickers appearing in multiple lists (potential crowding)
            lines.append("\n### Crowding Analysis")
            for ticker, mentions in sorted(all_tickers.items(), key=lambda x: -len(x[1])):
                avg_conviction = sum(m["conviction"] for m in mentions) / len(mentions)
                lines.append(f"- {ticker}: {len(mentions)} analyst(s), avg conviction {avg_conviction:.0f}")
                for mention in mentions:
                    lines.append(f"  - {mention['agent']}: {mention['conviction']}")

        # Add company risk data
        companies = data.get("companies", {})
        if companies:
            lines.append("\n## Risk Metrics")
            for ticker, company_data in companies.items():
                lines.append(f"\n### {ticker}")
                if isinstance(company_data, str):
                    lines.append(company_data)
                else:
                    fd = company_data.get("financial_data", {})
                    pd = company_data.get("price_data", {})

                    if fd or pd:
                        lines.extend([
                            f"- Beta: {fd.get('beta', 'N/A')}",
                            f"- Debt/Equity: {fd.get('debt_to_equity', 'N/A')}",
                            f"- Current Ratio: {fd.get('current_ratio', 'N/A')}",
                            f"- 52W High: ${fd.get('fifty_two_week_high', 'N/A')}",
                            f"- 52W Low: ${fd.get('fifty_two_week_low', 'N/A')}",
                        ])

                        # Calculate distance from 52W high/low
                        current = pd.get("current_price")
                        high = fd.get("fifty_two_week_high")
                        low = fd.get("fifty_two_week_low")
                        if current and high and low and high > low:
                            from_high = (current - high) / high * 100
                            from_low = (current - low) / low * 100
                            range_pct = (current - low) / (high - low) * 100
                            lines.extend([
                                f"- From 52W High: {from_high:.1f}%",
                                f"- From 52W Low: {from_low:.1f}%",
                                f"- 52W Range Position: {range_pct:.0f}%",
                            ])

        # Add short interest data if available
        short_interest = data.get("short_interest", {})
        if short_interest:
            lines.append("\n## Short Interest")
            for ticker, si in short_interest.items():
                lines.append(f"- {ticker}: {si}")

        # Add analyst sentiment (for contrarian view)
        analyst_ratings = data.get("analyst_ratings", {})
        if analyst_ratings:
            lines.append("\n## Analyst Consensus (Contrarian Signal)")
            for ticker, rating in analyst_ratings.items():
                lines.append(f"- {ticker}: {rating}")

        # Add macro risks
        macro_risks = data.get("macro_risks", [])
        if macro_risks:
            lines.extend([
                "",
                "## Macro Risk Factors",
            ])
            for risk in macro_risks:
                lines.append(f"- {risk}")

        return "\n".join(lines)
