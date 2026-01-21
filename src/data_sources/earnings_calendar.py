"""Earnings calendar and estimates data source."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
)

logger = logging.getLogger(__name__)


class EarningsCalendarDataSource(BaseDataSource):
    """Earnings calendar and estimates using Yahoo Finance API.

    Free, no API key required.
    """

    def __init__(self):
        """Initialize earnings calendar data source."""
        super().__init__(DataSourceType.FUNDAMENTAL)
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }
        )
        self._initialized = True

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch earnings data for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters

        Returns:
            DataSourceResult with earnings data
        """
        if not self._client:
            await self.initialize()

        try:
            # Try Yahoo Finance query
            earnings_data = await self._get_yahoo_earnings(ticker)

            if not earnings_data:
                return DataSourceResult(
                    source=DataSourceType.FUNDAMENTAL,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    data={
                        "ticker": ticker,
                        "error": "No earnings data available",
                    },
                )

            # Analyze earnings trends
            analysis = self._analyze_earnings(earnings_data)

            result_data = {
                "ticker": ticker,
                "source": "yahoo_finance",
                "timestamp": datetime.utcnow().isoformat(),
                "next_earnings": earnings_data.get("next_earnings"),
                "earnings_history": earnings_data.get("history", []),
                "estimates": earnings_data.get("estimates", {}),
                "analysis": analysis,
                "summary": self._generate_summary(ticker, earnings_data, analysis),
            }

            return DataSourceResult(
                source=DataSourceType.FUNDAMENTAL,
                ticker=ticker,
                quality=DataQuality.HIGH if earnings_data.get("history") else DataQuality.MEDIUM,
                data=result_data,
            )

        except Exception as e:
            logger.error(f"Earnings fetch error for {ticker}: {e}")
            return DataSourceResult(
                source=DataSourceType.FUNDAMENTAL,
                ticker=ticker,
                quality=DataQuality.UNKNOWN,
                error=str(e),
            )

    async def _get_yahoo_earnings(self, ticker: str) -> Optional[dict[str, Any]]:
        """Get earnings data from Yahoo Finance."""
        try:
            # Use yfinance-compatible API endpoint
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            params = {
                "modules": "earningsHistory,earningsTrend,calendarEvents"
            }

            response = await self._client.get(url, params=params)

            if response.status_code != 200:
                return None

            data = response.json()
            result = data.get("quoteSummary", {}).get("result", [])

            if not result:
                return None

            quote_data = result[0]

            earnings_data = {
                "history": [],
                "estimates": {},
                "next_earnings": None,
            }

            # Parse earnings history
            history = quote_data.get("earningsHistory", {}).get("history", [])
            for quarter in history:
                earnings_data["history"].append({
                    "quarter": quarter.get("quarter", {}).get("fmt"),
                    "date": quarter.get("quarterDate", {}).get("fmt"),
                    "eps_actual": quarter.get("epsActual", {}).get("raw"),
                    "eps_estimate": quarter.get("epsEstimate", {}).get("raw"),
                    "surprise_pct": quarter.get("surprisePercent", {}).get("raw"),
                })

            # Parse earnings trend/estimates
            trend = quote_data.get("earningsTrend", {}).get("trend", [])
            for period in trend:
                period_name = period.get("period", "unknown")
                earnings_data["estimates"][period_name] = {
                    "eps_estimate": period.get("earningsEstimate", {}).get("avg", {}).get("raw"),
                    "eps_low": period.get("earningsEstimate", {}).get("low", {}).get("raw"),
                    "eps_high": period.get("earningsEstimate", {}).get("high", {}).get("raw"),
                    "revenue_estimate": period.get("revenueEstimate", {}).get("avg", {}).get("raw"),
                    "growth": period.get("growth", {}).get("raw"),
                    "num_analysts": period.get("earningsEstimate", {}).get("numberOfAnalysts", {}).get("raw"),
                }

            # Parse calendar events (next earnings date)
            calendar = quote_data.get("calendarEvents", {}).get("earnings", {})
            earnings_date = calendar.get("earningsDate", [])
            if earnings_date:
                earnings_data["next_earnings"] = {
                    "date": earnings_date[0].get("fmt") if earnings_date else None,
                    "date_range_start": earnings_date[0].get("fmt") if len(earnings_date) > 0 else None,
                    "date_range_end": earnings_date[1].get("fmt") if len(earnings_date) > 1 else None,
                }

            return earnings_data

        except Exception as e:
            logger.warning(f"Yahoo Finance earnings API error: {e}")
            return None

    def _analyze_earnings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Analyze earnings trends and patterns."""
        history = data.get("history", [])

        if not history:
            return {"status": "no_data"}

        # Calculate beat/miss rate
        beats = sum(1 for q in history if q.get("surprise_pct", 0) and q["surprise_pct"] > 0)
        misses = sum(1 for q in history if q.get("surprise_pct", 0) and q["surprise_pct"] < 0)
        total = beats + misses

        beat_rate = (beats / total * 100) if total > 0 else 0

        # Calculate average surprise
        surprises = [q["surprise_pct"] for q in history if q.get("surprise_pct") is not None]
        avg_surprise = sum(surprises) / len(surprises) if surprises else 0

        # Trend analysis
        eps_values = [q["eps_actual"] for q in history if q.get("eps_actual") is not None]
        if len(eps_values) >= 2:
            if eps_values[0] > eps_values[-1]:
                trend = "growing"
            elif eps_values[0] < eps_values[-1]:
                trend = "declining"
            else:
                trend = "flat"
        else:
            trend = "unknown"

        # Estimate vs history
        estimates = data.get("estimates", {})
        current_estimate = estimates.get("0q", {}).get("eps_estimate")
        growth_next_q = estimates.get("0q", {}).get("growth")
        growth_next_y = estimates.get("+1y", {}).get("growth")

        return {
            "beat_rate": round(beat_rate, 1),
            "beats": beats,
            "misses": misses,
            "avg_surprise_pct": round(avg_surprise, 2) if avg_surprise else 0,
            "eps_trend": trend,
            "next_quarter_estimate": current_estimate,
            "next_quarter_growth": growth_next_q,
            "next_year_growth": growth_next_y,
            "consistency": "high" if beat_rate >= 75 else "medium" if beat_rate >= 50 else "low",
        }

    def _generate_summary(
        self,
        ticker: str,
        data: dict[str, Any],
        analysis: dict[str, Any],
    ) -> str:
        """Generate earnings summary."""
        parts = [f"Earnings for {ticker}:"]

        # Next earnings
        next_earnings = data.get("next_earnings", {})
        if next_earnings and next_earnings.get("date"):
            parts.append(f"Next report: {next_earnings['date']}")

        # Beat rate
        if analysis.get("beat_rate") is not None:
            parts.append(f"Beat rate: {analysis['beat_rate']:.0f}% ({analysis['beats']}/{analysis['beats']+analysis['misses']})")

        # Growth
        if analysis.get("next_year_growth"):
            growth = analysis["next_year_growth"] * 100
            parts.append(f"Expected YoY growth: {growth:+.1f}%")

        return " | ".join(parts)

    async def get_upcoming_earnings(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Get upcoming earnings dates for multiple tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            List of upcoming earnings sorted by date
        """
        upcoming = []

        for ticker in tickers:
            result = await self.fetch(ticker)
            if result.data and result.data.get("next_earnings"):
                next_date = result.data["next_earnings"].get("date")
                if next_date:
                    upcoming.append({
                        "ticker": ticker,
                        "date": next_date,
                        "estimate": result.data.get("analysis", {}).get("next_quarter_estimate"),
                    })

        # Sort by date
        upcoming.sort(key=lambda x: x.get("date", "9999-99-99"))
        return upcoming

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search is not supported - use fetch with ticker."""
        return [await self.fetch(query)]
