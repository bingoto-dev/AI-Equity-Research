"""Gamma Agent - AI Applications Specialist."""

from typing import Any, Dict, Optional

from src.agents.base import AgentOutput, Layer1Agent, StockPick
from src.llm.client import AgentLLMClient


class GammaAgent(Layer1Agent):
    """Gamma agent specializing in AI applications and vertical software."""

    # Default coverage universe for AI applications
    DEFAULT_TICKERS = [
        "TSLA", "ISRG", "DXCM", "VEEV",   # Healthcare/Robotics
        "ADBE", "INTU", "ADSK", "WDAY",   # Creative/Enterprise
        "AAPL", "SPOT", "PINS", "SNAP",   # Consumer
        "SYM", "PATH", "AI",              # Industrial/Pure-play AI
        "ABNB", "UBER", "DASH",           # Platform economy
        "ROK", "HON", "ABB",              # Industrial automation
    ]

    def __init__(
        self,
        name: str,
        system_prompt: str,
        sectors: list[str],
        llm_client: Optional[AgentLLMClient] = None,
    ):
        """Initialize Gamma agent.

        Args:
            name: Agent display name
            system_prompt: System prompt for the LLM
            sectors: List of sectors this agent covers
            llm_client: Optional LLM client (injected)
        """
        super().__init__(
            agent_id="gamma",
            name=name,
            system_prompt=system_prompt,
            sectors=sectors,
        )
        self.llm_client = llm_client
        self.coverage_tickers = self.DEFAULT_TICKERS.copy()

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
        """Analyze AI application companies.

        Args:
            data: Market data including company summaries
            context: Optional context (e.g., previous loop results)

        Returns:
            AgentOutput with top 5 AI application picks
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not set. Call set_llm_client first.")

        # Build data summary for the LLM
        data_summary = self._build_data_summary(data, context)

        # Get picks from LLM
        picks_data, response = await self.llm_client.get_top_picks(
            system_prompt=self.system_prompt,
            data_summary=data_summary,
            num_picks=5,
        )

        # Convert to StockPick objects
        picks = [StockPick(**pick) for pick in picks_data]

        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.name,
            layer=self.layer,
            picks=picks,
            reasoning=f"Analysis based on {len(data.get('companies', {}))} companies in AI applications sector.",
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "model": response.model,
                "sectors": self.sectors,
            },
        )

    def _build_data_summary(
        self,
        data: dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Build data summary for LLM consumption.

        Args:
            data: Raw market data
            context: Optional context

        Returns:
            Formatted data summary string
        """
        lines = [
            "# AI Applications Analysis",
            "",
            "## Coverage Universe",
            f"Focus: {', '.join(self.sectors)}",
            "",
        ]

        # Add company data
        companies = data.get("companies", {})
        if companies:
            lines.append("## Company Data")
            for ticker, company_data in companies.items():
                if ticker in self.coverage_tickers or self._is_relevant_sector(company_data):
                    lines.append(f"\n### {ticker}")
                    if isinstance(company_data, str):
                        lines.append(company_data)
                    else:
                        lines.append(str(company_data))

        # Add market context
        market_context = data.get("market_context", "")
        if market_context:
            lines.extend([
                "",
                "## Market Context",
                market_context,
            ])

        # Add vertical-specific trends
        vertical_trends = data.get("vertical_trends", {})
        if vertical_trends:
            lines.extend([
                "",
                "## Vertical Industry Trends",
            ])
            for vertical, trend in vertical_trends.items():
                lines.append(f"\n### {vertical}")
                lines.append(trend)

        # Add previous loop context if available
        if context and context.get("previous_picks"):
            lines.extend([
                "",
                "## Previous Analysis (for reference)",
                f"Previous picks: {', '.join(p.get('ticker', '') for p in context['previous_picks'])}",
            ])

        return "\n".join(lines)

    def _is_relevant_sector(self, company_data: Any) -> bool:
        """Check if company is in a relevant sector.

        Args:
            company_data: Company data dict or string

        Returns:
            True if relevant sector
        """
        relevant_terms = [
            "healthcare", "robotics", "autonomous", "automation",
            "consumer", "entertainment", "creative", "design",
            "industrial", "manufacturing", "medical",
        ]
        ai_terms = ["ai", "artificial intelligence", "machine learning", "neural"]

        # Handle case where company_data is a string instead of dict
        if isinstance(company_data, str):
            company_data_lower = company_data.lower()
            has_sector_match = any(term in company_data_lower for term in relevant_terms)
            has_ai_mention = any(term in company_data_lower for term in ai_terms)
            return has_sector_match or has_ai_mention

        if not isinstance(company_data, dict):
            return False

        sector = company_data.get("sector", "").lower()
        industry = company_data.get("industry", "").lower()
        description = company_data.get("description", "").lower()

        has_sector_match = any(term in sector or term in industry for term in relevant_terms)
        has_ai_mention = any(term in description for term in ai_terms)

        return has_sector_match or has_ai_mention

    def get_coverage_universe(self) -> list[str]:
        """Get the list of tickers this agent covers.

        Returns:
            List of ticker symbols
        """
        return self.coverage_tickers.copy()

    def add_to_coverage(self, ticker: str) -> None:
        """Add a ticker to coverage universe.

        Args:
            ticker: Ticker symbol to add
        """
        if ticker not in self.coverage_tickers:
            self.coverage_tickers.append(ticker)

    def remove_from_coverage(self, ticker: str) -> None:
        """Remove a ticker from coverage universe.

        Args:
            ticker: Ticker symbol to remove
        """
        if ticker in self.coverage_tickers:
            self.coverage_tickers.remove(ticker)
