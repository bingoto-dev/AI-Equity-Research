"""FRED API data source for macroeconomic indicators."""

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


class FREDMacroDataSource(BaseDataSource):
    """Federal Reserve Economic Data (FRED) API for macro indicators.

    Free API with 120 requests per minute limit.
    API key required (free registration at https://fred.stlouisfed.org/docs/api/api_key.html)
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    # Key macro indicators relevant to equity research
    INDICATORS = {
        # Interest rates & Fed
        "FEDFUNDS": {"name": "Federal Funds Rate", "category": "rates", "impact": "inverse"},
        "DGS10": {"name": "10-Year Treasury Yield", "category": "rates", "impact": "inverse"},
        "DGS2": {"name": "2-Year Treasury Yield", "category": "rates", "impact": "inverse"},
        "T10Y2Y": {"name": "10Y-2Y Spread (Yield Curve)", "category": "rates", "impact": "leading"},

        # Economic activity
        "GDP": {"name": "Real GDP", "category": "growth", "impact": "positive"},
        "UNRATE": {"name": "Unemployment Rate", "category": "labor", "impact": "inverse"},
        "PAYEMS": {"name": "Nonfarm Payrolls", "category": "labor", "impact": "positive"},
        "ICSA": {"name": "Initial Jobless Claims", "category": "labor", "impact": "inverse"},

        # Inflation
        "CPIAUCSL": {"name": "Consumer Price Index", "category": "inflation", "impact": "complex"},
        "PCEPI": {"name": "PCE Price Index", "category": "inflation", "impact": "complex"},
        "CORESTICKM159SFRBATL": {"name": "Sticky Core CPI", "category": "inflation", "impact": "complex"},

        # Tech & manufacturing
        "DGORDER": {"name": "Durable Goods Orders", "category": "manufacturing", "impact": "positive"},
        "INDPRO": {"name": "Industrial Production", "category": "manufacturing", "impact": "positive"},
        "TCU": {"name": "Capacity Utilization", "category": "manufacturing", "impact": "positive"},

        # Consumer
        "UMCSENT": {"name": "Consumer Sentiment", "category": "consumer", "impact": "positive"},
        "RSAFS": {"name": "Retail Sales", "category": "consumer", "impact": "positive"},

        # Financial conditions
        "VIXCLS": {"name": "VIX Volatility Index", "category": "volatility", "impact": "inverse"},
        "BAMLH0A0HYM2": {"name": "High Yield Spread", "category": "credit", "impact": "inverse"},
        "DTWEXBGS": {"name": "Dollar Index (Broad)", "category": "currency", "impact": "complex"},

        # Semiconductor specific
        "PCU334413334413": {"name": "Semiconductor PPI", "category": "tech", "impact": "complex"},
    }

    # Groups of indicators for different analysis needs
    INDICATOR_SETS = {
        "tech_relevant": ["FEDFUNDS", "DGS10", "VIXCLS", "INDPRO", "PCU334413334413"],
        "risk_assessment": ["T10Y2Y", "VIXCLS", "BAMLH0A0HYM2", "ICSA"],
        "growth_outlook": ["GDP", "PAYEMS", "INDPRO", "UMCSENT", "RSAFS"],
        "inflation_watch": ["CPIAUCSL", "PCEPI", "CORESTICKM159SFRBATL"],
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize FRED data source.

        Args:
            api_key: FRED API key (free at fred.stlouisfed.org)
        """
        super().__init__(DataSourceType.ECONOMIC)
        self._client: Optional[httpx.AsyncClient] = None
        self._api_key = api_key

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
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
        """Fetch macro context relevant for equity analysis.

        Args:
            ticker: Stock ticker (used to select relevant indicators)
            **kwargs: indicator_set (default: tech_relevant)

        Returns:
            DataSourceResult with macro data
        """
        if not self._api_key:
            return DataSourceResult(
                source=DataSourceType.ECONOMIC,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={
                    "error": "FRED API key not configured",
                    "summary": "Set DATA_FRED_API_KEY to enable macro data",
                },
            )

        if not self._client:
            await self.initialize()

        indicator_set = kwargs.get("indicator_set", "tech_relevant")
        indicators = self.INDICATOR_SETS.get(indicator_set, self.INDICATOR_SETS["tech_relevant"])

        results = {}
        for series_id in indicators:
            try:
                data = await self._get_series(series_id)
                if data:
                    results[series_id] = data
            except Exception as e:
                logger.warning(f"Failed to fetch {series_id}: {e}")

        if not results:
            return DataSourceResult(
                source=DataSourceType.ECONOMIC,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={"error": "Failed to fetch macro indicators"},
            )

        # Generate macro context summary
        summary = self._generate_macro_summary(results)

        result_data = {
            "ticker": ticker,
            "source": "fred",
            "timestamp": datetime.utcnow().isoformat(),
            "indicator_set": indicator_set,
            "indicators": results,
            "summary": summary,
            "context_for_equity": self._generate_equity_context(results),
        }

        return DataSourceResult(
            source=DataSourceType.ECONOMIC,
            ticker=ticker,
            quality=DataQuality.HIGH,
            data=result_data,
        )

    async def _get_series(self, series_id: str) -> Optional[dict[str, Any]]:
        """Get a single FRED series with recent observations."""
        # Get series info
        info_response = await self._client.get(
            f"{self.BASE_URL}/series",
            params={
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
            }
        )

        # Get observations
        obs_response = await self._client.get(
            f"{self.BASE_URL}/series/observations",
            params={
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 12,  # Last 12 observations
            }
        )

        if obs_response.status_code != 200:
            return None

        obs_data = obs_response.json()
        observations = obs_data.get("observations", [])

        if not observations:
            return None

        # Get indicator metadata
        indicator_info = self.INDICATORS.get(series_id, {})

        # Calculate changes
        values = []
        for obs in observations:
            try:
                val = float(obs.get("value", 0))
                values.append({"date": obs.get("date"), "value": val})
            except (ValueError, TypeError):
                continue

        if not values:
            return None

        latest = values[0]["value"]
        prev = values[1]["value"] if len(values) > 1 else latest
        year_ago = values[-1]["value"] if len(values) >= 12 else latest

        return {
            "series_id": series_id,
            "name": indicator_info.get("name", series_id),
            "category": indicator_info.get("category", "other"),
            "impact": indicator_info.get("impact", "complex"),
            "latest_value": latest,
            "latest_date": values[0]["date"],
            "change_period": round(latest - prev, 4),
            "change_yoy": round(latest - year_ago, 4) if year_ago else None,
            "change_pct": round((latest - prev) / abs(prev) * 100, 2) if prev != 0 else 0,
            "trend": "up" if latest > prev else "down" if latest < prev else "flat",
            "recent_observations": values[:6],
        }

    def _generate_macro_summary(self, results: dict[str, Any]) -> str:
        """Generate human-readable macro summary."""
        summaries = []

        # Fed funds rate
        if "FEDFUNDS" in results:
            rate = results["FEDFUNDS"]["latest_value"]
            trend = results["FEDFUNDS"]["trend"]
            summaries.append(f"Fed funds at {rate:.2f}% ({trend})")

        # Yield curve
        if "T10Y2Y" in results:
            spread = results["T10Y2Y"]["latest_value"]
            status = "inverted" if spread < 0 else "normal"
            summaries.append(f"Yield curve {status} ({spread:.2f}%)")

        # VIX
        if "VIXCLS" in results:
            vix = results["VIXCLS"]["latest_value"]
            level = "elevated" if vix > 20 else "low" if vix < 15 else "moderate"
            summaries.append(f"VIX {level} ({vix:.1f})")

        # Industrial production
        if "INDPRO" in results:
            change = results["INDPRO"]["change_pct"]
            direction = "expanding" if change > 0 else "contracting"
            summaries.append(f"Industrial production {direction} ({change:+.1f}%)")

        return "; ".join(summaries) if summaries else "Macro data unavailable"

    def _generate_equity_context(self, results: dict[str, Any]) -> str:
        """Generate equity market context from macro data."""
        signals = []

        # Interest rate environment
        if "FEDFUNDS" in results:
            rate = results["FEDFUNDS"]["latest_value"]
            if rate > 5:
                signals.append("High rate environment pressures growth stock valuations")
            elif rate < 2:
                signals.append("Low rates supportive of equity valuations")

        # Yield curve signal
        if "T10Y2Y" in results:
            spread = results["T10Y2Y"]["latest_value"]
            if spread < -0.5:
                signals.append("Deeply inverted yield curve: recession risk elevated")
            elif spread < 0:
                signals.append("Inverted yield curve: watch for economic slowdown")

        # VIX regime
        if "VIXCLS" in results:
            vix = results["VIXCLS"]["latest_value"]
            if vix > 30:
                signals.append("High volatility: risk-off environment")
            elif vix < 15:
                signals.append("Low volatility: complacency risk")

        # Credit conditions
        if "BAMLH0A0HYM2" in results:
            spread = results["BAMLH0A0HYM2"]["latest_value"]
            if spread > 5:
                signals.append("Wide credit spreads: financial stress")

        return " | ".join(signals) if signals else "Macro environment appears neutral"

    async def get_full_dashboard(self) -> dict[str, Any]:
        """Get comprehensive macro dashboard with all indicators."""
        if not self._api_key:
            return {"error": "API key not configured"}

        if not self._client:
            await self.initialize()

        all_results = {}
        for series_id in self.INDICATORS:
            try:
                data = await self._get_series(series_id)
                if data:
                    all_results[series_id] = data
            except Exception as e:
                logger.warning(f"Failed to fetch {series_id}: {e}")

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "indicators": all_results,
            "summary": self._generate_macro_summary(all_results),
            "categories": self._group_by_category(all_results),
        }

    def _group_by_category(self, results: dict[str, Any]) -> dict[str, list]:
        """Group indicators by category."""
        categories = {}
        for series_id, data in results.items():
            cat = data.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(data)
        return categories

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search FRED series."""
        return []
