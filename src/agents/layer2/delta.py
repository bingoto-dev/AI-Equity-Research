"""Delta Agent - Fundamental Analysis Specialist."""

from typing import Any, Dict, Optional

from src.agents.base import AgentOutput, Layer2Agent, StockPick
from src.llm.client import AgentLLMClient


class DeltaAgent(Layer2Agent):
    """Delta agent specializing in fundamental analysis."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        specialties: list[str],
        llm_client: Optional[AgentLLMClient] = None,
    ):
        """Initialize Delta agent.

        Args:
            name: Agent display name
            system_prompt: System prompt for the LLM
            specialties: List of analytical specialties
            llm_client: Optional LLM client (injected)
        """
        super().__init__(
            agent_id="delta",
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
        """Perform fundamental analysis on candidate companies.

        Args:
            data: Market data including Layer 1 outputs
            context: Optional context

        Returns:
            AgentOutput with top 5 fundamentally strong picks
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

        # Convert to StockPick objects and add fundamental scores
        picks = []
        for pick in picks_data:
            stock_pick = StockPick(**pick)
            # Add fundamental-specific scoring
            stock_pick.fundamental_score = pick.get("conviction_score", 50)
            picks.append(stock_pick)

        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.name,
            layer=self.layer,
            picks=picks,
            reasoning="Fundamental analysis focusing on valuation, quality, and capital allocation.",
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
            "# Fundamental Analysis - Layer 2",
            "",
            "## Your Role",
            "Analyze the combined candidate pool from Layer 1 analysts using fundamental metrics.",
            f"Focus: {', '.join(self.specialties)}",
            "",
        ]

        # Add Layer 1 candidate pool
        layer1_outputs = data.get("layer1_outputs", [])
        if layer1_outputs:
            lines.append("## Candidate Pool from Layer 1")
            all_tickers = set()
            for output in layer1_outputs:
                agent_name = output.get("agent_name", "Unknown")
                lines.append(f"\n### {agent_name}'s Picks")
                for pick in output.get("picks", []):
                    ticker = pick.get("ticker", "")
                    all_tickers.add(ticker)
                    lines.append(f"- {ticker}: {pick.get('thesis', '')[:100]}...")

            lines.extend([
                "",
                f"## Combined Candidates: {', '.join(sorted(all_tickers))}",
                "",
            ])

        # Add company financial data
        companies = data.get("companies", {})
        if companies:
            lines.append("## Financial Data")
            for ticker, company_data in companies.items():
                lines.append(f"\n### {ticker}")
                if isinstance(company_data, str):
                    lines.append(company_data)
                else:
                    # Extract key fundamental metrics
                    fd = company_data.get("financial_data", {})
                    if fd:
                        lines.extend([
                            f"- P/E: {fd.get('pe_ratio', 'N/A')}",
                            f"- Forward P/E: {fd.get('forward_pe', 'N/A')}",
                            f"- PEG: {fd.get('peg_ratio', 'N/A')}",
                            f"- EV/EBITDA: {fd.get('ev_to_ebitda', 'N/A')}",
                            f"- Profit Margin: {fd.get('profit_margin', 'N/A')}",
                            f"- ROE: {fd.get('return_on_equity', 'N/A')}",
                            f"- Debt/Equity: {fd.get('debt_to_equity', 'N/A')}",
                            f"- Revenue Growth: {fd.get('revenue_growth', 'N/A')}",
                        ])

        # Add valuation context
        valuation_context = data.get("valuation_context", "")
        if valuation_context:
            lines.extend([
                "",
                "## Valuation Context",
                valuation_context,
            ])

        return "\n".join(lines)
