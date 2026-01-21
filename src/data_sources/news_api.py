"""NewsAPI data source for news articles."""

from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    NewsArticle,
)


class NewsAPIDataSource(BaseDataSource):
    """NewsAPI data source for company news."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: str):
        """Initialize NewsAPI data source.

        Args:
            api_key: NewsAPI API key
        """
        super().__init__(DataSourceType.NEWS_API)
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            headers={"X-Api-Key": self.api_key},
            timeout=30.0,
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
        """Fetch news for a company/ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters (company_name, days_back, page_size)

        Returns:
            DataSourceResult with news articles
        """
        if not self._client:
            await self.initialize()

        company_name = kwargs.get("company_name", ticker)
        days_back = kwargs.get("days_back", 7)
        page_size = kwargs.get("page_size", 20)

        try:
            from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

            # Search for company news
            params = {
                "q": f'"{company_name}" OR "{ticker}"',
                "from": from_date,
                "sortBy": "relevancy",
                "pageSize": page_size,
                "language": "en",
            }

            response = await self._client.get(f"{self.BASE_URL}/everything", params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for article in data.get("articles", []):
                published_at = article.get("publishedAt")
                if published_at:
                    try:
                        published_dt = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_dt = datetime.utcnow()
                else:
                    published_dt = datetime.utcnow()

                news_article = NewsArticle(
                    ticker=ticker,
                    title=article.get("title", ""),
                    description=article.get("description"),
                    content=article.get("content"),
                    url=article.get("url", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    published_at=published_dt,
                )
                articles.append(news_article)

            return DataSourceResult(
                source=DataSourceType.NEWS_API,
                ticker=ticker,
                quality=DataQuality.MEDIUM if articles else DataQuality.LOW,
                news=articles,
                data={
                    "total_results": data.get("totalResults", 0),
                    "query": params["q"],
                },
            )

        except Exception as e:
            return DataSourceResult(
                source=DataSourceType.NEWS_API,
                ticker=ticker,
                quality=DataQuality.LOW,
                error=str(e),
            )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search for news articles.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of results (single result containing matching articles)
        """
        if not self._client:
            await self.initialize()

        days_back = kwargs.get("days_back", 7)
        page_size = kwargs.get("page_size", 20)

        try:
            from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

            params = {
                "q": query,
                "from": from_date,
                "sortBy": "relevancy",
                "pageSize": page_size,
                "language": "en",
            }

            response = await self._client.get(f"{self.BASE_URL}/everything", params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for article in data.get("articles", []):
                published_at = article.get("publishedAt")
                if published_at:
                    try:
                        published_dt = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_dt = datetime.utcnow()
                else:
                    published_dt = datetime.utcnow()

                news_article = NewsArticle(
                    title=article.get("title", ""),
                    description=article.get("description"),
                    content=article.get("content"),
                    url=article.get("url", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    published_at=published_dt,
                )
                articles.append(news_article)

            return [
                DataSourceResult(
                    source=DataSourceType.NEWS_API,
                    quality=DataQuality.MEDIUM if articles else DataQuality.LOW,
                    news=articles,
                    data={
                        "total_results": data.get("totalResults", 0),
                        "query": query,
                    },
                )
            ]

        except Exception as e:
            return [
                DataSourceResult(
                    source=DataSourceType.NEWS_API,
                    quality=DataQuality.LOW,
                    error=str(e),
                )
            ]

    async def get_top_headlines(
        self,
        category: str = "business",
        country: str = "us",
        page_size: int = 20,
    ) -> list[NewsArticle]:
        """Get top headlines.

        Args:
            category: News category
            country: Country code
            page_size: Number of results

        Returns:
            List of news articles
        """
        if not self._client:
            await self.initialize()

        try:
            params = {
                "category": category,
                "country": country,
                "pageSize": page_size,
            }

            response = await self._client.get(f"{self.BASE_URL}/top-headlines", params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for article in data.get("articles", []):
                published_at = article.get("publishedAt")
                if published_at:
                    try:
                        published_dt = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_dt = datetime.utcnow()
                else:
                    published_dt = datetime.utcnow()

                news_article = NewsArticle(
                    title=article.get("title", ""),
                    description=article.get("description"),
                    content=article.get("content"),
                    url=article.get("url", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    published_at=published_dt,
                )
                articles.append(news_article)

            return articles

        except Exception:
            return []
