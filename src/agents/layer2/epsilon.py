"""Epsilon Agent - Technical & Quantitative Analysis Specialist."""

from typing import Any, Dict, Optional

from src.agents.base import AgentOutput, Layer2Agent, StockPick
from src.llm.client import AgentLLMClient


class EpsilonAgent(Layer2Agent):
    """Epsilon agent specializing in technical and momentum analysis."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        specialties: list[str],
        llm_client: Optional[AgentLLMClient] = None,
    ):
        """Initialize Epsilon agent.

        Args:
            name: Agent display name
            system_prompt: System prompt for the LLM
            specialties: List of analytical specialties
            llm_client: Optional LLM client (injected)
        """
        super().__init__(
            agent_id="epsilon",
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
        """Perform technical analysis on candidate companies.

        Args:
            data: Market data including Layer 1 outputs
            context: Optional context

        Returns:
            AgentOutput with top 5 technically strong picks
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

        # Convert to StockPick objects and add technical scores
        picks = []
        for pick in picks_data:
            stock_pick = StockPick(**pick)
            # Add technical-specific scoring
            stock_pick.technical_score = pick.get("conviction_score", 50)
            picks.append(stock_pick)

        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.name,
            layer=self.layer,
            picks=picks,
            reasoning="Technical analysis focusing on momentum, trends, and institutional flows.",
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
            "# Technical & Momentum Analysis - Layer 2",
            "",
            "## Your Role",
            "Analyze the combined candidate pool from Layer 1 using technical and momentum factors.",
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
                    lines.append(f"- {ticker}: Conviction {pick.get('conviction_score', 'N/A')}")

            lines.extend([
                "",
                f"## Combined Candidates: {', '.join(sorted(all_tickers))}",
                "",
            ])

        # Add company price/technical data
        companies = data.get("companies", {})
        if companies:
            lines.append("## Price & Technical Data")
            for ticker, company_data in companies.items():
                lines.append(f"\n### {ticker}")
                if isinstance(company_data, str):
                    lines.append(company_data)
                else:
                    # Extract key technical metrics
                    pd = company_data.get("price_data", {})
                    if pd:
                        lines.extend([
                            f"- Current Price: ${pd.get('current_price', 'N/A')}",
                            f"- 50-Day SMA: ${pd.get('sma_50', 'N/A')}",
                            f"- 200-Day SMA: ${pd.get('sma_200', 'N/A')}",
                            f"- RSI (14): {pd.get('rsi_14', 'N/A')}",
                            f"- MACD: {pd.get('macd', 'N/A')}",
                            f"- 1D Change: {pd.get('change_1d', 'N/A')}",
                            f"- 1M Change: {pd.get('change_1m', 'N/A')}",
                            f"- YTD Change: {pd.get('change_ytd', 'N/A')}",
                            f"- Relative Volume: {pd.get('relative_volume', 'N/A')}",
                        ])

                    # Add price vs moving averages
                    current = pd.get("current_price")
                    sma50 = pd.get("sma_50")
                    sma200 = pd.get("sma_200")
                    if current and sma50 and sma200:
                        above_50 = "Above" if current > sma50 else "Below"
                        above_200 = "Above" if current > sma200 else "Below"
                        lines.append(f"- Position: {above_50} 50-SMA, {above_200} 200-SMA")

        # Add market context
        market_context = data.get("market_context", "")
        if market_context:
            lines.extend([
                "",
                "## Market Context",
                market_context,
            ])

        # Add sector relative performance
        sector_performance = data.get("sector_performance", {})
        if sector_performance:
            lines.extend([
                "",
                "## Sector Relative Performance",
            ])
            for sector, perf in sector_performance.items():
                lines.append(f"- {sector}: {perf}")

        return "\n".join(lines)
