"""Reddit API data source for retail sentiment from investing subreddits."""

import asyncio
import logging
import re
import time
from collections import Counter
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

# Global rate limiter for Reddit (10 requests per minute for unauthenticated)
_reddit_last_request = 0.0
_reddit_min_interval = 6.0  # seconds between requests (10/min)


class RedditSentimentDataSource(BaseDataSource):
    """Reddit sentiment analysis for retail investor signals.

    Uses Reddit's public JSON endpoints (no API key required).
    Monitors: wallstreetbets, stocks, investing, SecurityAnalysis
    """

    # Subreddits to monitor for financial content
    SUBREDDITS = [
        "wallstreetbets",
        "stocks",
        "investing",
        "SecurityAnalysis",
        "options",
        "stockmarket",
    ]

    # Common ticker pattern
    TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b')

    # Words that look like tickers but aren't
    FALSE_POSITIVES = {
        "CEO", "CFO", "CTO", "COO", "IPO", "ETF", "GDP", "USD", "EUR",
        "USA", "UK", "FBI", "SEC", "FDA", "EPA", "IRS", "IMF", "WSB",
        "DD", "YOLO", "FD", "ITM", "OTM", "ATM", "EPS", "PE", "PB",
        "RSI", "MACD", "SMA", "EMA", "IV", "DTE", "OP", "TL", "DR",
        "EDIT", "TLDR", "IMO", "IMHO", "FYI", "BTW", "LOL", "WTF",
        "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL",
        "CAN", "HAD", "HER", "WAS", "ONE", "OUR", "OUT", "HAS",
        "HIS", "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "SEE",
        "WAY", "WHO", "BOY", "DID", "GET", "HIM", "LET", "PUT",
        "SAY", "SHE", "TOO", "USE", "API", "AI", "ML", "GPU", "CPU",
    }

    def __init__(self):
        """Initialize Reddit data source."""
        super().__init__(DataSourceType.SOCIAL)
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "AI-Equity-Research/1.0 (educational research)"
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
        """Fetch Reddit mentions and sentiment for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters (subreddits, time_filter)

        Returns:
            DataSourceResult with Reddit sentiment data
        """
        if not self._client:
            await self.initialize()

        # Default to just wallstreetbets for speed (add more via kwargs if needed)
        subreddits = kwargs.get("subreddits", ["wallstreetbets"])
        time_filter = kwargs.get("time_filter", "week")

        all_mentions = []
        total_score = 0
        total_comments = 0

        for subreddit in subreddits:
            try:
                mentions = await self._search_subreddit(ticker, subreddit, time_filter)
                all_mentions.extend(mentions)
                for m in mentions:
                    total_score += m.get("score", 0)
                    total_comments += m.get("num_comments", 0)
            except Exception as e:
                logger.warning(f"Failed to search r/{subreddit} for {ticker}: {e}")

        if not all_mentions:
            return DataSourceResult(
                source=DataSourceType.SOCIAL,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={
                    "ticker": ticker,
                    "mention_count": 0,
                    "summary": f"No recent Reddit mentions found for ${ticker}",
                },
            )

        # Analyze sentiment from titles and engagement
        sentiment_score = self._analyze_sentiment(all_mentions)

        # Sort by engagement
        all_mentions.sort(key=lambda x: x.get("score", 0) + x.get("num_comments", 0), reverse=True)

        result_data = {
            "ticker": ticker,
            "source": "reddit",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "mention_count": len(all_mentions),
                "total_upvotes": total_score,
                "total_comments": total_comments,
                "avg_engagement": (total_score + total_comments) / len(all_mentions) if all_mentions else 0,
            },
            "sentiment": {
                "score": sentiment_score,
                "label": self._sentiment_label(sentiment_score),
            },
            "top_posts": all_mentions[:10],
            "subreddits_searched": subreddits,
            "summary": self._generate_summary(ticker, all_mentions, sentiment_score),
        }

        quality = DataQuality.MEDIUM if len(all_mentions) >= 5 else DataQuality.LOW

        return DataSourceResult(
            source=DataSourceType.SOCIAL,
            ticker=ticker,
            quality=quality,
            data=result_data,
        )

    async def _search_subreddit(
        self,
        ticker: str,
        subreddit: str,
        time_filter: str,
    ) -> list[dict[str, Any]]:
        """Search a subreddit for ticker mentions."""
        global _reddit_last_request

        # Rate limiting - wait if needed
        elapsed = time.time() - _reddit_last_request
        if elapsed < _reddit_min_interval:
            wait_time = _reddit_min_interval - elapsed
            logger.debug(f"Reddit rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        _reddit_last_request = time.time()

        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": f"${ticker} OR {ticker}",
            "restrict_sr": "true",
            "sort": "relevance",
            "t": time_filter,
            "limit": 25,
        }

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "title": post.get("title", ""),
                "subreddit": subreddit,
                "score": post.get("score", 0),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "num_comments": post.get("num_comments", 0),
                "created_utc": post.get("created_utc"),
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "flair": post.get("link_flair_text"),
            })

        return posts

    def _analyze_sentiment(self, mentions: list[dict[str, Any]]) -> float:
        """Analyze sentiment from post titles and engagement.

        Returns score from -100 to +100.
        """
        if not mentions:
            return 0.0

        positive_words = {
            "moon", "rocket", "bullish", "buy", "calls", "long", "gains",
            "winner", "growth", "strong", "beat", "upgrade", "breakout",
            "squeeze", "tendies", "diamond", "hands", "hold", "accumulate",
        }
        negative_words = {
            "crash", "bearish", "sell", "puts", "short", "loss", "dump",
            "loser", "weak", "miss", "downgrade", "breakdown", "baghold",
            "tank", "drill", "rip", "dead", "overvalued", "bubble",
        }

        positive_count = 0
        negative_count = 0
        weighted_score = 0

        for mention in mentions:
            title = mention.get("title", "").lower()
            weight = 1 + (mention.get("score", 0) / 100)  # Weight by engagement

            for word in positive_words:
                if word in title:
                    positive_count += 1
                    weighted_score += weight

            for word in negative_words:
                if word in title:
                    negative_count += 1
                    weighted_score -= weight

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        # Normalize to -100 to +100
        raw_score = weighted_score / len(mentions) * 20
        return max(-100, min(100, raw_score))

    def _sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label."""
        if score > 30:
            return "bullish"
        elif score > 10:
            return "slightly bullish"
        elif score > -10:
            return "neutral"
        elif score > -30:
            return "slightly bearish"
        else:
            return "bearish"

    def _generate_summary(
        self,
        ticker: str,
        mentions: list[dict[str, Any]],
        sentiment_score: float,
    ) -> str:
        """Generate summary of Reddit activity."""
        total_engagement = sum(m.get("score", 0) + m.get("num_comments", 0) for m in mentions)

        subreddits = Counter(m.get("subreddit") for m in mentions)
        top_sub = subreddits.most_common(1)[0][0] if subreddits else "N/A"

        return (
            f"Reddit sentiment for ${ticker}: {self._sentiment_label(sentiment_score)} "
            f"(score: {sentiment_score:+.1f}). "
            f"Found {len(mentions)} posts with {total_engagement:,} total engagement. "
            f"Most active in r/{top_sub}."
        )

    async def get_trending_tickers(self, subreddit: str = "wallstreetbets") -> list[dict[str, Any]]:
        """Extract trending tickers from a subreddit's hot posts.

        Returns:
            List of tickers with mention counts
        """
        global _reddit_last_request

        if not self._client:
            await self.initialize()

        # Rate limiting
        elapsed = time.time() - _reddit_last_request
        if elapsed < _reddit_min_interval:
            await asyncio.sleep(_reddit_min_interval - elapsed)
        _reddit_last_request = time.time()

        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json"
            response = await self._client.get(url, params={"limit": 50})
            response.raise_for_status()
            data = response.json()

            ticker_counts = Counter()

            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = post.get("title", "") + " " + post.get("selftext", "")

                # Extract tickers
                for match in self.TICKER_PATTERN.finditer(title):
                    ticker = match.group(1) or match.group(2)
                    if ticker and ticker not in self.FALSE_POSITIVES and len(ticker) >= 2:
                        ticker_counts[ticker] += 1

            # Return top tickers
            return [
                {"ticker": ticker, "mentions": count, "subreddit": subreddit}
                for ticker, count in ticker_counts.most_common(20)
            ]

        except Exception as e:
            logger.error(f"Failed to get trending tickers from r/{subreddit}: {e}")
            return []

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search Reddit for a query across financial subreddits."""
        results = []
        for subreddit in self.SUBREDDITS[:3]:
            result = await self.fetch(query, subreddits=[subreddit])
            results.append(result)
        return results
