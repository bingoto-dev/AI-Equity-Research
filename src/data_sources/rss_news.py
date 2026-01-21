"""RSS feed aggregator for financial news."""

import logging
import re
from datetime import datetime
from typing import Any, Optional
from xml.etree import ElementTree

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    NewsArticle,
)

logger = logging.getLogger(__name__)


class RSSNewsDataSource(BaseDataSource):
    """RSS feed aggregator for financial news from multiple sources.

    No API key required - uses public RSS feeds.
    """

    # Financial news RSS feeds
    RSS_FEEDS = {
        # Major financial news
        "yahoo_finance": {
            "url": "https://finance.yahoo.com/rss/topstories",
            "name": "Yahoo Finance",
            "category": "general",
        },
        "reuters_business": {
            "url": "https://news.google.com/rss/search?q=site:reuters.com+business&hl=en-US&gl=US&ceid=US:en",
            "name": "Reuters Business",
            "category": "general",
        },
        "cnbc": {
            "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "name": "CNBC",
            "category": "general",
        },
        "marketwatch": {
            "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
            "name": "MarketWatch",
            "category": "general",
        },
        "seeking_alpha": {
            "url": "https://seekingalpha.com/market_currents.xml",
            "name": "Seeking Alpha",
            "category": "analysis",
        },

        # Tech-focused
        "techcrunch": {
            "url": "https://techcrunch.com/feed/",
            "name": "TechCrunch",
            "category": "tech",
        },
        "the_verge": {
            "url": "https://www.theverge.com/rss/index.xml",
            "name": "The Verge",
            "category": "tech",
        },
        "ars_technica": {
            "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
            "name": "Ars Technica",
            "category": "tech",
        },

        # AI-specific
        "ai_news": {
            "url": "https://news.google.com/rss/search?q=artificial+intelligence+company&hl=en-US&gl=US&ceid=US:en",
            "name": "AI News (Google)",
            "category": "ai",
        },
        "nvidia_news": {
            "url": "https://news.google.com/rss/search?q=NVIDIA&hl=en-US&gl=US&ceid=US:en",
            "name": "NVIDIA News",
            "category": "company",
        },
    }

    # Company-specific feed templates
    COMPANY_FEED_TEMPLATE = "https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"

    def __init__(self):
        """Initialize RSS news data source."""
        super().__init__(DataSourceType.NEWS)
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "AI-Equity-Research/1.0 (RSS aggregator)",
            },
            follow_redirects=True,
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
        """Fetch news for a specific ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: include_general (bool), max_articles (int)

        Returns:
            DataSourceResult with news articles
        """
        if not self._client:
            await self.initialize()

        include_general = kwargs.get("include_general", False)
        max_articles = kwargs.get("max_articles", 20)

        articles = []

        # Fetch ticker-specific news from Google News
        ticker_feed_url = self.COMPANY_FEED_TEMPLATE.format(ticker=ticker)
        ticker_articles = await self._fetch_feed(ticker_feed_url, f"{ticker} News")

        # Filter for relevance
        for article in ticker_articles:
            if self._is_relevant(article, ticker):
                articles.append(article)

        # Optionally include general market news
        if include_general:
            for feed_id in ["yahoo_finance", "seeking_alpha"]:
                feed_info = self.RSS_FEEDS.get(feed_id)
                if feed_info:
                    general_articles = await self._fetch_feed(
                        feed_info["url"],
                        feed_info["name"]
                    )
                    # Only include if mentions our ticker
                    for article in general_articles:
                        if ticker.upper() in article.get("title", "").upper():
                            articles.append(article)

        # Dedupe by title
        seen_titles = set()
        unique_articles = []
        for article in articles:
            title = article.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_articles.append(article)

        # Sort by date and limit
        unique_articles.sort(
            key=lambda x: x.get("published", ""),
            reverse=True
        )
        unique_articles = unique_articles[:max_articles]

        # Convert to NewsArticle objects
        news_articles = [
            NewsArticle(
                title=a.get("title", ""),
                url=a.get("link", ""),
                source=a.get("source", "RSS"),
                published_at=self._parse_date(a.get("published")),
                summary=a.get("summary", "")[:500],
            )
            for a in unique_articles
        ]

        result_data = {
            "ticker": ticker,
            "source": "rss_aggregator",
            "timestamp": datetime.utcnow().isoformat(),
            "article_count": len(news_articles),
            "articles": [
                {
                    "title": a.title,
                    "url": a.url,
                    "source": a.source,
                    "published": a.published_at.isoformat() if a.published_at else None,
                    "summary": a.summary,
                }
                for a in news_articles
            ],
            "summary": self._generate_summary(ticker, news_articles),
        }

        return DataSourceResult(
            source=DataSourceType.NEWS,
            ticker=ticker,
            quality=DataQuality.MEDIUM if len(news_articles) >= 3 else DataQuality.LOW,
            news=news_articles,
            data=result_data,
        )

    async def _fetch_feed(self, url: str, source_name: str) -> list[dict[str, Any]]:
        """Fetch and parse an RSS feed."""
        try:
            response = await self._client.get(url)
            response.raise_for_status()

            articles = []
            root = ElementTree.fromstring(response.content)

            # Handle both RSS 2.0 and Atom formats
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items[:30]:  # Limit per feed
                article = self._parse_item(item, source_name)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed {url}: {e}")
            return []

    def _parse_item(self, item: ElementTree.Element, source_name: str) -> Optional[dict[str, Any]]:
        """Parse an RSS item element."""
        # Try RSS 2.0 format
        title = item.findtext("title")
        link = item.findtext("link")
        pub_date = item.findtext("pubDate")
        description = item.findtext("description")

        # Try Atom format if RSS fields not found
        if not title:
            title = item.findtext("{http://www.w3.org/2005/Atom}title")
        if not link:
            link_elem = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_elem.get("href") if link_elem is not None else None
        if not pub_date:
            pub_date = item.findtext("{http://www.w3.org/2005/Atom}updated")
        if not description:
            description = item.findtext("{http://www.w3.org/2005/Atom}summary")

        if not title or not link:
            return None

        # Clean up description (remove HTML tags)
        if description:
            description = re.sub(r'<[^>]+>', '', description)
            description = description.strip()[:500]

        return {
            "title": title.strip(),
            "link": link.strip(),
            "published": pub_date,
            "summary": description or "",
            "source": source_name,
        }

    def _is_relevant(self, article: dict[str, Any], ticker: str) -> bool:
        """Check if article is relevant to the ticker."""
        text = (article.get("title", "") + " " + article.get("summary", "")).upper()
        return ticker.upper() in text

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RSS 2.0
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _generate_summary(self, ticker: str, articles: list[NewsArticle]) -> str:
        """Generate news summary."""
        if not articles:
            return f"No recent news found for {ticker}"

        sources = set(a.source for a in articles)
        return (
            f"Found {len(articles)} news articles for {ticker} "
            f"from {len(sources)} sources. "
            f"Latest: \"{articles[0].title[:80]}...\""
        )

    async def get_market_headlines(self, max_articles: int = 30) -> list[dict[str, Any]]:
        """Get general market headlines from all feeds.

        Returns:
            List of headline articles
        """
        if not self._client:
            await self.initialize()

        all_articles = []

        for feed_id, feed_info in self.RSS_FEEDS.items():
            if feed_info["category"] in ["general", "analysis"]:
                articles = await self._fetch_feed(feed_info["url"], feed_info["name"])
                all_articles.extend(articles)

        # Sort by date
        all_articles.sort(key=lambda x: x.get("published", ""), reverse=True)

        # Dedupe
        seen = set()
        unique = []
        for article in all_articles:
            title = article.get("title", "")
            if title not in seen:
                seen.add(title)
                unique.append(article)

        return unique[:max_articles]

    async def get_tech_news(self, max_articles: int = 20) -> list[dict[str, Any]]:
        """Get tech-focused news.

        Returns:
            List of tech news articles
        """
        if not self._client:
            await self.initialize()

        all_articles = []

        for feed_id, feed_info in self.RSS_FEEDS.items():
            if feed_info["category"] in ["tech", "ai"]:
                articles = await self._fetch_feed(feed_info["url"], feed_info["name"])
                all_articles.extend(articles)

        all_articles.sort(key=lambda x: x.get("published", ""), reverse=True)
        return all_articles[:max_articles]

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search news for a query."""
        # Use Google News RSS for search
        search_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        articles = await self._fetch_feed(search_url, "Google News")

        return [
            DataSourceResult(
                source=DataSourceType.NEWS,
                quality=DataQuality.MEDIUM,
                data=article,
            )
            for article in articles[:10]
        ]
