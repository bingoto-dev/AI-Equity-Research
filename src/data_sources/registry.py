"""Data source registry and plugin management."""

from typing import Any, Optional

from src.data_sources.base import BaseDataSource, DataSourceResult, DataSourceType


class DataSourceRegistry:
    """Registry for managing data source plugins."""

    def __init__(self):
        """Initialize the registry."""
        self._sources: dict[DataSourceType, BaseDataSource] = {}
        self._initialized = False

    def register(self, source: BaseDataSource) -> None:
        """Register a data source.

        Args:
            source: Data source instance to register
        """
        self._sources[source.source_type] = source

    def unregister(self, source_type: DataSourceType) -> None:
        """Unregister a data source.

        Args:
            source_type: Type of source to remove
        """
        self._sources.pop(source_type, None)

    def get(self, source_type: DataSourceType) -> Optional[BaseDataSource]:
        """Get a registered data source.

        Args:
            source_type: Type of source to retrieve

        Returns:
            The data source or None if not found
        """
        return self._sources.get(source_type)

    def get_all(self) -> list[BaseDataSource]:
        """Get all registered data sources.

        Returns:
            List of all registered sources
        """
        return list(self._sources.values())

    def get_available_types(self) -> list[DataSourceType]:
        """Get list of available data source types.

        Returns:
            List of registered source types
        """
        return list(self._sources.keys())

    async def initialize_all(self) -> dict[DataSourceType, bool]:
        """Initialize all registered data sources.

        Returns:
            Dict mapping source type to initialization success
        """
        results = {}
        for source_type, source in self._sources.items():
            try:
                await source.initialize()
                results[source_type] = True
            except Exception:
                results[source_type] = False
        self._initialized = True
        return results

    async def close_all(self) -> None:
        """Close all data sources."""
        for source in self._sources.values():
            await source.close()
        self._initialized = False

    async def fetch_from_all(
        self,
        ticker: str,
        source_types: Optional[list[DataSourceType]] = None,
    ) -> dict[DataSourceType, DataSourceResult]:
        """Fetch data for a ticker from multiple sources.

        Args:
            ticker: Stock ticker symbol
            source_types: Optional list of specific sources to use

        Returns:
            Dict mapping source type to result
        """
        results = {}
        sources_to_query = (
            [self._sources[st] for st in source_types if st in self._sources]
            if source_types
            else self._sources.values()
        )

        for source in sources_to_query:
            try:
                result = await source.fetch(ticker)
                results[source.source_type] = result
            except Exception as e:
                results[source.source_type] = DataSourceResult(
                    source=source.source_type,
                    ticker=ticker,
                    error=str(e),
                )

        return results

    async def health_check_all(self) -> dict[DataSourceType, bool]:
        """Check health of all data sources.

        Returns:
            Dict mapping source type to health status
        """
        results = {}
        for source_type, source in self._sources.items():
            results[source_type] = await source.health_check()
        return results


def create_default_registry(
    news_api_key: Optional[str] = None,
    alpha_vantage_key: Optional[str] = None,
    sec_user_agent: Optional[str] = None,
    fred_api_key: Optional[str] = None,
    github_token: Optional[str] = None,
) -> DataSourceRegistry:
    """Create a registry with default data sources.

    Args:
        news_api_key: Optional NewsAPI key
        alpha_vantage_key: Optional Alpha Vantage key
        sec_user_agent: SEC EDGAR user agent string
        fred_api_key: Optional FRED API key for macro data
        github_token: Optional GitHub token for higher rate limits

    Returns:
        Configured DataSourceRegistry
    """
    from src.data_sources.alpha_vantage import AlphaVantageDataSource
    from src.data_sources.news_api import NewsAPIDataSource
    from src.data_sources.sec_edgar import SECEdgarDataSource
    from src.data_sources.twitter_stub import TwitterStubDataSource
    from src.data_sources.web_search import WebSearchDataSource
    from src.data_sources.yahoo_finance import YahooFinanceDataSource

    # New data sources
    from src.data_sources.stocktwits import StockTwitsDataSource
    from src.data_sources.reddit_sentiment import RedditSentimentDataSource
    from src.data_sources.github_tracker import GitHubTrackerDataSource
    from src.data_sources.sec_insider import SECInsiderDataSource
    from src.data_sources.fred_macro import FREDMacroDataSource
    from src.data_sources.rss_news import RSSNewsDataSource
    from src.data_sources.earnings_calendar import EarningsCalendarDataSource
    from src.data_sources.fintwit import FinTwitDataSource

    registry = DataSourceRegistry()

    # Always available sources (no API key required)
    registry.register(YahooFinanceDataSource())
    registry.register(WebSearchDataSource())
    registry.register(TwitterStubDataSource())

    # New free sources (no API key required)
    registry.register(StockTwitsDataSource())
    registry.register(RedditSentimentDataSource())
    registry.register(GitHubTrackerDataSource(token=github_token))
    registry.register(RSSNewsDataSource())
    registry.register(EarningsCalendarDataSource())
    registry.register(FinTwitDataSource())

    # SEC EDGAR sources (requires user agent)
    if sec_user_agent:
        registry.register(SECEdgarDataSource(user_agent=sec_user_agent))
        registry.register(SECInsiderDataSource(user_agent=sec_user_agent))

    # Optional API-key sources
    if news_api_key:
        registry.register(NewsAPIDataSource(api_key=news_api_key))

    if alpha_vantage_key:
        registry.register(AlphaVantageDataSource(api_key=alpha_vantage_key))

    if fred_api_key:
        registry.register(FREDMacroDataSource(api_key=fred_api_key))

    return registry


def create_enhanced_registry(
    news_api_key: Optional[str] = None,
    alpha_vantage_key: Optional[str] = None,
    sec_user_agent: Optional[str] = None,
    fred_api_key: Optional[str] = None,
    github_token: Optional[str] = None,
) -> DataSourceRegistry:
    """Create an enhanced registry with all available data sources.

    This is the recommended registry for production use with maximum
    data coverage for the research agents.

    Args:
        All keys are optional but improve data quality when provided

    Returns:
        Fully configured DataSourceRegistry
    """
    return create_default_registry(
        news_api_key=news_api_key,
        alpha_vantage_key=alpha_vantage_key,
        sec_user_agent=sec_user_agent or "AI-Equity-Research research@example.com",
        fred_api_key=fred_api_key,
        github_token=github_token,
    )
