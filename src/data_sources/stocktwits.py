"""StockTwits API data source for social sentiment."""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
)

logger = logging.getLogger(__name__)


class StockTwitsDataSource(BaseDataSource):
    """StockTwits API for retail sentiment and social signals.

    Free API with no authentication required for basic endpoints.
    Rate limit: 200 requests per hour.
    """

    BASE_URL = "https://api.stocktwits.com/api/2"

    def __init__(self):
        """Initialize StockTwits data source."""
        super().__init__(DataSourceType.SOCIAL)
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

    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch StockTwits sentiment for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters

        Returns:
            DataSourceResult with sentiment data
        """
        if not self._client:
            await self.initialize()

        try:
            # Get symbol stream
            response = await self._client.get(
                f"{self.BASE_URL}/streams/symbol/{ticker}.json",
                params={"limit": 30}  # Get last 30 messages
            )

            if response.status_code == 404:
                return DataSourceResult(
                    source=DataSourceType.SOCIAL,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    data={"error": "Symbol not found on StockTwits"},
                )

            response.raise_for_status()
            data = response.json()

            # Parse sentiment
            symbol_data = data.get("symbol", {})
            messages = data.get("messages", [])

            # Calculate sentiment metrics
            bullish = 0
            bearish = 0
            neutral = 0
            total_with_sentiment = 0

            for msg in messages:
                sentiment = msg.get("entities", {}).get("sentiment")
                if sentiment:
                    total_with_sentiment += 1
                    if sentiment.get("basic") == "Bullish":
                        bullish += 1
                    elif sentiment.get("basic") == "Bearish":
                        bearish += 1
                    else:
                        neutral += 1

            # Calculate sentiment score (-100 to +100)
            if total_with_sentiment > 0:
                sentiment_score = ((bullish - bearish) / total_with_sentiment) * 100
            else:
                sentiment_score = 0

            # Extract trending info
            watchlist_count = symbol_data.get("watchlist_count", 0)

            # Get recent message highlights
            recent_messages = []
            for msg in messages[:10]:
                recent_messages.append({
                    "body": msg.get("body", "")[:200],
                    "sentiment": msg.get("entities", {}).get("sentiment", {}).get("basic"),
                    "created_at": msg.get("created_at"),
                    "likes": msg.get("likes", {}).get("total", 0),
                })

            result_data = {
                "ticker": ticker,
                "source": "stocktwits",
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": {
                    "score": round(sentiment_score, 2),
                    "bullish_count": bullish,
                    "bearish_count": bearish,
                    "neutral_count": neutral,
                    "total_with_sentiment": total_with_sentiment,
                    "total_messages": len(messages),
                },
                "popularity": {
                    "watchlist_count": watchlist_count,
                    "message_volume": len(messages),
                },
                "recent_messages": recent_messages,
                "summary": self._generate_summary(
                    ticker, sentiment_score, bullish, bearish, len(messages), watchlist_count
                ),
            }

            return DataSourceResult(
                source=DataSourceType.SOCIAL,
                ticker=ticker,
                quality=DataQuality.MEDIUM if total_with_sentiment >= 5 else DataQuality.LOW,
                data=result_data,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.warning(f"StockTwits API requires authentication for {ticker}")
                return DataSourceResult(
                    source=DataSourceType.SOCIAL,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    data={
                        "error": "StockTwits API now requires authentication",
                        "summary": f"StockTwits data unavailable for ${ticker} - API authentication required",
                    },
                )
            logger.error(f"StockTwits API error for {ticker}: {e}")
            return DataSourceResult(
                source=DataSourceType.SOCIAL,
                ticker=ticker,
                quality=DataQuality.UNKNOWN,
                error=f"StockTwits API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"StockTwits fetch error for {ticker}: {e}")
            return DataSourceResult(
                source=DataSourceType.SOCIAL,
                ticker=ticker,
                quality=DataQuality.UNKNOWN,
                error=str(e),
            )

    def _generate_summary(
        self,
        ticker: str,
        sentiment_score: float,
        bullish: int,
        bearish: int,
        message_count: int,
        watchlist_count: int,
    ) -> str:
        """Generate human-readable sentiment summary."""
        if sentiment_score > 50:
            sentiment_label = "strongly bullish"
        elif sentiment_score > 20:
            sentiment_label = "moderately bullish"
        elif sentiment_score > -20:
            sentiment_label = "neutral"
        elif sentiment_score > -50:
            sentiment_label = "moderately bearish"
        else:
            sentiment_label = "strongly bearish"

        return (
            f"StockTwits sentiment for ${ticker}: {sentiment_label} "
            f"(score: {sentiment_score:+.1f}). "
            f"{bullish} bullish vs {bearish} bearish posts in last {message_count} messages. "
            f"Watchlist count: {watchlist_count:,}."
        )

    async def get_trending(self) -> list[dict[str, Any]]:
        """Get trending symbols on StockTwits.

        Returns:
            List of trending symbols with metadata
        """
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get(f"{self.BASE_URL}/trending/symbols.json")
            response.raise_for_status()
            data = response.json()

            symbols = []
            for sym in data.get("symbols", []):
                symbols.append({
                    "ticker": sym.get("symbol"),
                    "title": sym.get("title"),
                    "watchlist_count": sym.get("watchlist_count", 0),
                })

            return symbols

        except Exception as e:
            logger.error(f"Failed to get StockTwits trending: {e}")
            return []

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search is not supported for StockTwits."""
        return []
