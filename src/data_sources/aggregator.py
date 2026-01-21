"""Data aggregator that combines multiple data sources."""

import asyncio
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.data_sources.base import (
    CompanyProfile,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    FinancialData,
    NewsArticle,
    PriceData,
    SECFiling,
)
from src.data_sources.registry import DataSourceRegistry


class AggregatedCompanyData(BaseModel):
    """Aggregated data for a company from all sources."""

    ticker: str
    company_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Core data
    profile: Optional[CompanyProfile] = None
    financial_data: Optional[FinancialData] = None
    price_data: Optional[PriceData] = None

    # Collections
    news: list[NewsArticle] = Field(default_factory=list)
    filings: list[SECFiling] = Field(default_factory=list)

    # Source tracking
    sources_used: list[DataSourceType] = Field(default_factory=list)
    sources_failed: list[DataSourceType] = Field(default_factory=list)
    overall_quality: DataQuality = DataQuality.UNKNOWN

    # Raw results for debugging
    raw_results: dict[str, DataSourceResult] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class DataAggregator:
    """Aggregates data from multiple sources into unified company data."""

    def __init__(self, registry: DataSourceRegistry):
        """Initialize the aggregator.

        Args:
            registry: Data source registry with initialized sources
        """
        self.registry = registry

    async def get_company_data(
        self,
        ticker: str,
        company_name: Optional[str] = None,
        include_sources: Optional[list[DataSourceType]] = None,
        exclude_sources: Optional[list[DataSourceType]] = None,
    ) -> AggregatedCompanyData:
        """Get aggregated data for a company.

        Args:
            ticker: Stock ticker symbol
            company_name: Optional company name for better search
            include_sources: Specific sources to include (None = all)
            exclude_sources: Sources to exclude

        Returns:
            AggregatedCompanyData with combined results
        """
        # Determine which sources to use
        available_sources = set(self.registry.get_available_types())

        if include_sources:
            sources_to_use = set(include_sources) & available_sources
        else:
            sources_to_use = available_sources

        if exclude_sources:
            sources_to_use -= set(exclude_sources)

        # Fetch from all sources in parallel
        tasks = []
        source_list = list(sources_to_use)

        for source_type in source_list:
            source = self.registry.get(source_type)
            if source:
                # Add company name for news/web sources
                kwargs = {}
                if company_name:
                    kwargs["company_name"] = company_name

                tasks.append(source.fetch(ticker, **kwargs))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        aggregated = AggregatedCompanyData(
            ticker=ticker,
            company_name=company_name or ticker,
        )

        sources_succeeded = []
        sources_failed = []

        for i, result in enumerate(results):
            source_type = source_list[i]

            if isinstance(result, Exception):
                sources_failed.append(source_type)
                continue

            if result.error:
                sources_failed.append(source_type)
                aggregated.raw_results[source_type.value] = result
                continue

            sources_succeeded.append(source_type)
            aggregated.raw_results[source_type.value] = result

            # Merge profile (prefer Yahoo Finance)
            if result.profile:
                if not aggregated.profile or source_type == DataSourceType.YAHOO_FINANCE:
                    aggregated.profile = result.profile
                    if not company_name:
                        aggregated.company_name = result.profile.name

            # Merge financial data (prefer Alpha Vantage, then Yahoo)
            if result.financial_data:
                if not aggregated.financial_data:
                    aggregated.financial_data = result.financial_data
                elif source_type == DataSourceType.ALPHA_VANTAGE:
                    # Merge Alpha Vantage data into existing
                    aggregated.financial_data = self._merge_financial_data(
                        aggregated.financial_data,
                        result.financial_data,
                    )

            # Merge price data (prefer Yahoo Finance)
            if result.price_data:
                if not aggregated.price_data or source_type == DataSourceType.YAHOO_FINANCE:
                    aggregated.price_data = result.price_data

            # Aggregate news
            aggregated.news.extend(result.news)

            # Aggregate filings
            aggregated.filings.extend(result.filings)

        # Sort news by date
        aggregated.news.sort(key=lambda x: x.published_at, reverse=True)

        # Sort filings by date
        aggregated.filings.sort(key=lambda x: x.filing_date, reverse=True)

        # Set source tracking
        aggregated.sources_used = sources_succeeded
        aggregated.sources_failed = sources_failed

        # Determine overall quality
        aggregated.overall_quality = self._calculate_overall_quality(
            sources_succeeded,
            sources_failed,
        )

        return aggregated

    async def get_batch_data(
        self,
        tickers: list[str],
        **kwargs: Any,
    ) -> dict[str, AggregatedCompanyData]:
        """Get aggregated data for multiple tickers.

        Args:
            tickers: List of stock ticker symbols
            **kwargs: Additional parameters passed to get_company_data

        Returns:
            Dict mapping ticker to aggregated data
        """
        tasks = [self.get_company_data(ticker, **kwargs) for ticker in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            ticker: result if not isinstance(result, Exception)
            else AggregatedCompanyData(
                ticker=ticker,
                company_name=ticker,
                overall_quality=DataQuality.LOW,
            )
            for ticker, result in zip(tickers, results)
        }

    async def search_companies(
        self,
        query: str,
        limit: int = 10,
    ) -> list[AggregatedCompanyData]:
        """Search for companies and return aggregated data.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of aggregated company data
        """
        # Search across sources
        found_tickers = set()

        for source in self.registry.get_all():
            try:
                results = await source.search(query)
                for result in results:
                    if result.ticker:
                        found_tickers.add(result.ticker)
            except Exception:
                continue

        # Limit and fetch full data
        tickers_to_fetch = list(found_tickers)[:limit]
        batch_data = await self.get_batch_data(tickers_to_fetch)

        return list(batch_data.values())

    def _merge_financial_data(
        self,
        base: FinancialData,
        new: FinancialData,
    ) -> FinancialData:
        """Merge two financial data objects, preferring non-None values.

        Args:
            base: Base financial data
            new: New data to merge in

        Returns:
            Merged financial data
        """
        merged_dict = base.model_dump()

        for field, value in new.model_dump().items():
            if value is not None and merged_dict.get(field) is None:
                merged_dict[field] = value

        return FinancialData(**merged_dict)

    def _calculate_overall_quality(
        self,
        succeeded: list[DataSourceType],
        failed: list[DataSourceType],
    ) -> DataQuality:
        """Calculate overall data quality.

        Args:
            succeeded: Sources that succeeded
            failed: Sources that failed

        Returns:
            Overall quality assessment
        """
        if not succeeded:
            return DataQuality.LOW

        # High quality sources
        high_quality = {DataSourceType.YAHOO_FINANCE, DataSourceType.SEC_EDGAR}
        medium_quality = {DataSourceType.ALPHA_VANTAGE, DataSourceType.NEWS_API}

        has_high = any(s in high_quality for s in succeeded)
        has_medium = any(s in medium_quality for s in succeeded)

        if has_high and len(succeeded) >= 3:
            return DataQuality.HIGH
        elif has_high or (has_medium and len(succeeded) >= 2):
            return DataQuality.MEDIUM
        else:
            return DataQuality.LOW

    def get_data_summary(self, data: AggregatedCompanyData) -> str:
        """Get a text summary of aggregated data.

        Args:
            data: Aggregated company data

        Returns:
            Text summary for LLM consumption
        """
        lines = [
            f"# {data.company_name} ({data.ticker})",
            f"Data Quality: {data.overall_quality.value}",
            f"Sources: {', '.join(s.value for s in data.sources_used)}",
            "",
        ]

        if data.profile:
            lines.extend([
                "## Company Profile",
                f"Sector: {data.profile.sector}",
                f"Industry: {data.profile.industry}",
                f"Employees: {data.profile.employees:,}" if data.profile.employees else "",
                "",
            ])

        if data.financial_data:
            fd = data.financial_data
            lines.extend([
                "## Financial Metrics",
                f"Market Cap: ${fd.market_cap:,.0f}" if fd.market_cap else "",
                f"P/E Ratio: {fd.pe_ratio:.2f}" if fd.pe_ratio else "",
                f"Forward P/E: {fd.forward_pe:.2f}" if fd.forward_pe else "",
                f"PEG Ratio: {fd.peg_ratio:.2f}" if fd.peg_ratio else "",
                f"EV/EBITDA: {fd.ev_to_ebitda:.2f}" if fd.ev_to_ebitda else "",
                f"Profit Margin: {fd.profit_margin:.1%}" if fd.profit_margin else "",
                f"ROE: {fd.return_on_equity:.1%}" if fd.return_on_equity else "",
                f"Revenue Growth: {fd.revenue_growth:.1%}" if fd.revenue_growth else "",
                f"Debt/Equity: {fd.debt_to_equity:.2f}" if fd.debt_to_equity else "",
                "",
            ])

        if data.price_data:
            pd = data.price_data
            lines.extend([
                "## Price Data",
                f"Current Price: ${pd.current_price:.2f}",
                f"50-Day SMA: ${pd.sma_50:.2f}" if pd.sma_50 else "",
                f"200-Day SMA: ${pd.sma_200:.2f}" if pd.sma_200 else "",
                f"RSI (14): {pd.rsi_14:.1f}" if pd.rsi_14 else "",
                "",
            ])

        if data.news[:5]:
            lines.extend([
                "## Recent News",
            ])
            for article in data.news[:5]:
                lines.append(f"- {article.title} ({article.source})")
            lines.append("")

        if data.filings[:3]:
            lines.extend([
                "## Recent SEC Filings",
            ])
            for filing in data.filings[:3]:
                lines.append(f"- {filing.form_type}: {filing.filing_date.strftime('%Y-%m-%d')}")
            lines.append("")

        # Filter empty lines at the end
        return "\n".join(line for line in lines if line or line == "")
