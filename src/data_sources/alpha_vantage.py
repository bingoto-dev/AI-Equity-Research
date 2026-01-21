"""Alpha Vantage data source for fundamental and technical data."""

from datetime import datetime
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    FinancialData,
    PriceData,
)


class AlphaVantageDataSource(BaseDataSource):
    """Alpha Vantage data source for fundamentals and technicals."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        """Initialize Alpha Vantage data source.

        Args:
            api_key: Alpha Vantage API key
        """
        super().__init__(DataSourceType.ALPHA_VANTAGE)
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
        self._initialized = True

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def _make_request(self, params: dict[str, str]) -> dict[str, Any]:
        """Make API request with common parameters.

        Args:
            params: Request parameters

        Returns:
            JSON response data
        """
        params["apikey"] = self.api_key
        response = await self._client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        return response.json()

    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch fundamental data for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters

        Returns:
            DataSourceResult with fundamental data
        """
        if not self._client:
            await self.initialize()

        try:
            # Get company overview
            overview = await self._make_request({
                "function": "OVERVIEW",
                "symbol": ticker,
            })

            if "Error Message" in overview or not overview:
                return DataSourceResult(
                    source=DataSourceType.ALPHA_VANTAGE,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    error=overview.get("Error Message", "No data found"),
                )

            # Build financial data
            financial_data = FinancialData(
                ticker=ticker,
                company_name=overview.get("Name", ticker),
                market_cap=self._parse_float(overview.get("MarketCapitalization")),
                pe_ratio=self._parse_float(overview.get("TrailingPE")),
                forward_pe=self._parse_float(overview.get("ForwardPE")),
                peg_ratio=self._parse_float(overview.get("PEGRatio")),
                price_to_book=self._parse_float(overview.get("PriceToBookRatio")),
                price_to_sales=self._parse_float(overview.get("PriceToSalesRatioTTM")),
                ev_to_ebitda=self._parse_float(overview.get("EVToEBITDA")),
                profit_margin=self._parse_float(overview.get("ProfitMargin")),
                operating_margin=self._parse_float(overview.get("OperatingMarginTTM")),
                return_on_equity=self._parse_float(overview.get("ReturnOnEquityTTM")),
                return_on_assets=self._parse_float(overview.get("ReturnOnAssetsTTM")),
                revenue_growth=self._parse_float(overview.get("QuarterlyRevenueGrowthYOY")),
                earnings_growth=self._parse_float(overview.get("QuarterlyEarningsGrowthYOY")),
                dividend_yield=self._parse_float(overview.get("DividendYield")),
                beta=self._parse_float(overview.get("Beta")),
                fifty_two_week_high=self._parse_float(overview.get("52WeekHigh")),
                fifty_two_week_low=self._parse_float(overview.get("52WeekLow")),
                shares_outstanding=self._parse_float(overview.get("SharesOutstanding")),
            )

            return DataSourceResult(
                source=DataSourceType.ALPHA_VANTAGE,
                ticker=ticker,
                quality=DataQuality.HIGH,
                financial_data=financial_data,
                data={
                    "overview": overview,
                    "sector": overview.get("Sector"),
                    "industry": overview.get("Industry"),
                    "description": overview.get("Description"),
                },
            )

        except Exception as e:
            return DataSourceResult(
                source=DataSourceType.ALPHA_VANTAGE,
                ticker=ticker,
                quality=DataQuality.LOW,
                error=str(e),
            )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search for tickers.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of matching results
        """
        if not self._client:
            await self.initialize()

        try:
            data = await self._make_request({
                "function": "SYMBOL_SEARCH",
                "keywords": query,
            })

            results = []
            for match in data.get("bestMatches", [])[:5]:
                ticker = match.get("1. symbol")
                if ticker:
                    result = await self.fetch(ticker)
                    results.append(result)

            return results

        except Exception:
            return []

    async def get_income_statement(self, ticker: str) -> dict[str, Any]:
        """Get income statement data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Income statement data
        """
        if not self._client:
            await self.initialize()

        try:
            return await self._make_request({
                "function": "INCOME_STATEMENT",
                "symbol": ticker,
            })
        except Exception as e:
            return {"error": str(e)}

    async def get_balance_sheet(self, ticker: str) -> dict[str, Any]:
        """Get balance sheet data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Balance sheet data
        """
        if not self._client:
            await self.initialize()

        try:
            return await self._make_request({
                "function": "BALANCE_SHEET",
                "symbol": ticker,
            })
        except Exception as e:
            return {"error": str(e)}

    async def get_cash_flow(self, ticker: str) -> dict[str, Any]:
        """Get cash flow statement data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Cash flow data
        """
        if not self._client:
            await self.initialize()

        try:
            return await self._make_request({
                "function": "CASH_FLOW",
                "symbol": ticker,
            })
        except Exception as e:
            return {"error": str(e)}

    async def get_earnings(self, ticker: str) -> dict[str, Any]:
        """Get earnings data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Earnings data
        """
        if not self._client:
            await self.initialize()

        try:
            return await self._make_request({
                "function": "EARNINGS",
                "symbol": ticker,
            })
        except Exception as e:
            return {"error": str(e)}

    async def get_rsi(self, ticker: str, interval: str = "daily", period: int = 14) -> dict[str, Any]:
        """Get RSI technical indicator.

        Args:
            ticker: Stock ticker symbol
            interval: Time interval
            period: RSI period

        Returns:
            RSI data
        """
        if not self._client:
            await self.initialize()

        try:
            return await self._make_request({
                "function": "RSI",
                "symbol": ticker,
                "interval": interval,
                "time_period": str(period),
                "series_type": "close",
            })
        except Exception as e:
            return {"error": str(e)}

    async def get_macd(self, ticker: str, interval: str = "daily") -> dict[str, Any]:
        """Get MACD technical indicator.

        Args:
            ticker: Stock ticker symbol
            interval: Time interval

        Returns:
            MACD data
        """
        if not self._client:
            await self.initialize()

        try:
            return await self._make_request({
                "function": "MACD",
                "symbol": ticker,
                "interval": interval,
                "series_type": "close",
            })
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _parse_float(value: Optional[str]) -> Optional[float]:
        """Parse a string to float, returning None for invalid values.

        Args:
            value: String value to parse

        Returns:
            Float value or None
        """
        if not value or value in ("None", "-", "N/A"):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
