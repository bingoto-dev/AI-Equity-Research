"""Web search data source for research and analysis."""

from datetime import datetime
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    NewsArticle,
)


class WebSearchDataSource(BaseDataSource):
    """Web search data source using DuckDuckGo (no API key required)."""

    # DuckDuckGo instant answers API (limited but free)
    DDG_API_URL = "https://api.duckduckgo.com/"

    def __init__(self):
        """Initialize web search data source."""
        super().__init__(DataSourceType.WEB_SEARCH)
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AI-Equity-Research/1.0)",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self._initialized = True

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch web search results for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters (company_name, query_type)

        Returns:
            DataSourceResult with search results
        """
        if not self._client:
            await self.initialize()

        company_name = kwargs.get("company_name", ticker)
        query_type = kwargs.get("query_type", "general")

        # Build query based on type
        queries = {
            "general": f"{company_name} {ticker} stock analysis",
            "news": f"{company_name} {ticker} latest news",
            "earnings": f"{company_name} {ticker} earnings report",
            "analyst": f"{company_name} {ticker} analyst rating",
            "ai": f"{company_name} {ticker} AI artificial intelligence strategy",
        }

        query = queries.get(query_type, queries["general"])

        try:
            # Use DuckDuckGo instant answers
            params = {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            }

            response = await self._client.get(self.DDG_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            articles = []

            # Process abstract
            if data.get("Abstract"):
                articles.append(
                    NewsArticle(
                        ticker=ticker,
                        title=data.get("Heading", f"About {company_name}"),
                        description=data.get("Abstract"),
                        url=data.get("AbstractURL", ""),
                        source=data.get("AbstractSource", "Web"),
                        published_at=datetime.utcnow(),
                    )
                )

            # Process related topics
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    articles.append(
                        NewsArticle(
                            ticker=ticker,
                            title=topic.get("Text", "")[:100],
                            description=topic.get("Text"),
                            url=topic.get("FirstURL", ""),
                            source="DuckDuckGo",
                            published_at=datetime.utcnow(),
                        )
                    )

            # Process results
            for result in data.get("Results", [])[:5]:
                if isinstance(result, dict):
                    articles.append(
                        NewsArticle(
                            ticker=ticker,
                            title=result.get("Text", "")[:100],
                            description=result.get("Text"),
                            url=result.get("FirstURL", ""),
                            source="DuckDuckGo",
                            published_at=datetime.utcnow(),
                        )
                    )

            return DataSourceResult(
                source=DataSourceType.WEB_SEARCH,
                ticker=ticker,
                quality=DataQuality.MEDIUM if articles else DataQuality.LOW,
                news=articles,
                data={
                    "query": query,
                    "query_type": query_type,
                    "definition": data.get("Definition"),
                    "definition_source": data.get("DefinitionSource"),
                },
            )

        except Exception as e:
            return DataSourceResult(
                source=DataSourceType.WEB_SEARCH,
                ticker=ticker,
                quality=DataQuality.LOW,
                error=str(e),
            )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search the web for a query.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        if not self._client:
            await self.initialize()

        try:
            params = {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            }

            response = await self._client.get(self.DDG_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            articles = []

            if data.get("Abstract"):
                articles.append(
                    NewsArticle(
                        title=data.get("Heading", query),
                        description=data.get("Abstract"),
                        url=data.get("AbstractURL", ""),
                        source=data.get("AbstractSource", "Web"),
                        published_at=datetime.utcnow(),
                    )
                )

            for topic in data.get("RelatedTopics", [])[:10]:
                if isinstance(topic, dict) and topic.get("Text"):
                    articles.append(
                        NewsArticle(
                            title=topic.get("Text", "")[:100],
                            description=topic.get("Text"),
                            url=topic.get("FirstURL", ""),
                            source="DuckDuckGo",
                            published_at=datetime.utcnow(),
                        )
                    )

            return [
                DataSourceResult(
                    source=DataSourceType.WEB_SEARCH,
                    quality=DataQuality.MEDIUM if articles else DataQuality.LOW,
                    news=articles,
                    data={"query": query},
                )
            ]

        except Exception as e:
            return [
                DataSourceResult(
                    source=DataSourceType.WEB_SEARCH,
                    quality=DataQuality.LOW,
                    error=str(e),
                )
            ]

    async def get_company_info(self, company_name: str) -> dict[str, Any]:
        """Get general company information from web.

        Args:
            company_name: Company name to search

        Returns:
            Dict with company information
        """
        if not self._client:
            await self.initialize()

        try:
            params = {
                "q": company_name,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            }

            response = await self._client.get(self.DDG_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "name": company_name,
                "heading": data.get("Heading"),
                "abstract": data.get("Abstract"),
                "abstract_source": data.get("AbstractSource"),
                "abstract_url": data.get("AbstractURL"),
                "definition": data.get("Definition"),
                "image": data.get("Image"),
                "infobox": data.get("Infobox", {}),
            }

        except Exception as e:
            return {"name": company_name, "error": str(e)}
