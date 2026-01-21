"""Yahoo Finance data source."""

from datetime import datetime
from typing import Any

import yfinance as yf

from src.data_sources.base import (
    BaseDataSource,
    CompanyProfile,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    FinancialData,
    PriceData,
)


class YahooFinanceDataSource(BaseDataSource):
    """Yahoo Finance data source for stock data and fundamentals."""

    def __init__(self):
        """Initialize Yahoo Finance data source."""
        super().__init__(DataSourceType.YAHOO_FINANCE)

    async def initialize(self) -> None:
        """Initialize the data source."""
        self._initialized = True

    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch comprehensive data for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters (period, interval for history)

        Returns:
            DataSourceResult with financial and price data
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Build financial data
            financial_data = FinancialData(
                ticker=ticker,
                company_name=info.get("longName", info.get("shortName", ticker)),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                forward_pe=info.get("forwardPE"),
                peg_ratio=info.get("pegRatio"),
                price_to_book=info.get("priceToBook"),
                price_to_sales=info.get("priceToSalesTrailing12Months"),
                ev_to_ebitda=info.get("enterpriseToEbitda"),
                profit_margin=info.get("profitMargins"),
                operating_margin=info.get("operatingMargins"),
                return_on_equity=info.get("returnOnEquity"),
                return_on_assets=info.get("returnOnAssets"),
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                debt_to_equity=info.get("debtToEquity"),
                current_ratio=info.get("currentRatio"),
                free_cash_flow=info.get("freeCashflow"),
                dividend_yield=info.get("dividendYield"),
                beta=info.get("beta"),
                fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                fifty_two_week_low=info.get("fiftyTwoWeekLow"),
                avg_volume=info.get("averageVolume"),
                shares_outstanding=info.get("sharesOutstanding"),
            )

            # Build price data
            current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            price_data = PriceData(
                ticker=ticker,
                current_price=current_price,
                previous_close=info.get("previousClose", 0),
                open_price=info.get("open", 0),
                day_high=info.get("dayHigh", 0),
                day_low=info.get("dayLow", 0),
                volume=info.get("volume", 0),
                sma_50=info.get("fiftyDayAverage"),
                sma_200=info.get("twoHundredDayAverage"),
            )

            # Calculate percentage changes if data available
            if price_data.previous_close and price_data.previous_close > 0:
                price_data.change_1d = (
                    (current_price - price_data.previous_close) / price_data.previous_close
                )

            # Build company profile
            profile = CompanyProfile(
                ticker=ticker,
                name=info.get("longName", info.get("shortName", ticker)),
                sector=info.get("sector"),
                industry=info.get("industry"),
                description=info.get("longBusinessSummary"),
                website=info.get("website"),
                employees=info.get("fullTimeEmployees"),
                headquarters=f"{info.get('city', '')}, {info.get('state', '')} {info.get('country', '')}".strip(
                    ", "
                ),
                exchange=info.get("exchange"),
            )

            return DataSourceResult(
                source=DataSourceType.YAHOO_FINANCE,
                ticker=ticker,
                quality=DataQuality.HIGH,
                financial_data=financial_data,
                price_data=price_data,
                profile=profile,
                data={"raw_info": info},
            )

        except Exception as e:
            return DataSourceResult(
                source=DataSourceType.YAHOO_FINANCE,
                ticker=ticker,
                quality=DataQuality.LOW,
                error=str(e),
            )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search for tickers matching a query.

        Args:
            query: Search query (company name or partial ticker)
            **kwargs: Additional parameters

        Returns:
            List of matching results
        """
        results = []
        try:
            # Use yfinance Tickers for multiple symbols
            tickers = yf.Tickers(query)
            for ticker_symbol in tickers.tickers:
                result = await self.fetch(ticker_symbol)
                if not result.error:
                    results.append(result)
        except Exception:
            pass
        return results

    async def get_historical_data(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Get historical price data.

        Args:
            ticker: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            Dict with historical price data
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)
            return {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "data": hist.to_dict() if not hist.empty else {},
            }
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    async def get_options_data(self, ticker: str) -> dict[str, Any]:
        """Get options chain data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with options data
        """
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            options_data = {}
            for exp in expirations[:3]:  # Limit to first 3 expirations
                options_data[exp] = {
                    "calls": stock.option_chain(exp).calls.to_dict(),
                    "puts": stock.option_chain(exp).puts.to_dict(),
                }
            return {"ticker": ticker, "expirations": expirations, "chains": options_data}
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    async def get_institutional_holders(self, ticker: str) -> list[dict[str, Any]]:
        """Get institutional holders.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of institutional holders
        """
        try:
            stock = yf.Ticker(ticker)
            holders = stock.institutional_holders
            if holders is not None and not holders.empty:
                return holders.to_dict("records")
            return []
        except Exception:
            return []
