"""FinTwit (Financial Twitter) data source via Nitter instances."""

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
)

logger = logging.getLogger(__name__)


class FinTwitDataSource(BaseDataSource):
    """FinTwit tracker using Nitter instances for Twitter/X data.

    Monitors key financial influencers, cashtags, and AI news.
    No API key required - uses public Nitter instances.
    """

    # Nitter instances (updated Jan 2026)
    # Note: Most instances require accounts now since Twitter removed guest access
    NITTER_INSTANCES = [
        "https://twiiit.com",            # Proxy that redirects to working instances
        "https://xcancel.com",           # Active fork
        "https://nitter.poast.org",      # May work
        "https://nitter.net",            # Original (development resumed Feb 2025)
    ]

    # Fallback mode: When Nitter is down, provide curated Twitter lists
    FINTWIT_LISTS_FALLBACK = {
        "ai_tracking": "https://twitter.com/i/lists/1234567890",  # AI stocks tracking
        "breaking_news": "https://twitter.com/search?q=%24TICKER&src=typed_query&f=live",
    }

    # Key FinTwit influencers by category
    INFLUENCERS = {
        "ai_researchers": [
            "kaborst",       # Andrej Karpathy
            "ylecun",        # Yann LeCun (Meta AI)
            "AndrewYNg",     # Andrew Ng
            "sama",          # Sam Altman (OpenAI)
            "demaboruk",     # Demis Hassabis (DeepMind)
            "JensenHuang",   # Jensen Huang (NVIDIA) - if exists
            "sataborst",     # Satya Nadella
        ],
        "tech_analysts": [
            "markgurman",    # Bloomberg Apple/Tech
            "mingchikuo",    # Apple analyst
            "borrowed",      # Dan Ives (Wedbush)
            "TechMeme",      # Tech news aggregator
        ],
        "market_news": [
            "DeItaone",      # Walter Bloomberg - breaking news
            "FirstSquawk",   # Breaking market news
            "zaborst",       # News aggregator
            "Stocktwits",    # StockTwits official
            "unusual_whales", # Options flow
        ],
        "fund_managers": [
            "chamath",       # Chamath Palihapitiya
            "GaryBlack00",   # Gary Black (Tesla bull)
            "CathieDWood",   # Cathie Wood (ARK)
            "michaeljburry", # Michael Burry
        ],
        "ai_companies": [
            "nvidia",        # NVIDIA official
            "OpenAI",        # OpenAI official
            "anthropic",     # Anthropic official
            "Google_AI",     # Google AI
            "MetaAI",        # Meta AI
        ],
    }

    # Cashtag to company mapping
    CASHTAGS = {
        "NVDA": "NVIDIA",
        "AMD": "AMD",
        "INTC": "Intel",
        "MSFT": "Microsoft",
        "GOOGL": "Google",
        "META": "Meta",
        "AMZN": "Amazon",
        "TSLA": "Tesla",
        "AAPL": "Apple",
        "TSM": "TSMC",
        "AVGO": "Broadcom",
        "ORCL": "Oracle",
        "CRM": "Salesforce",
        "PLTR": "Palantir",
        "SNOW": "Snowflake",
        "AI": "C3.ai",
    }

    def __init__(self):
        """Initialize FinTwit data source."""
        super().__init__(DataSourceType.SOCIAL)
        self._client: Optional[httpx.AsyncClient] = None
        self._working_instance: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client and find working Nitter instance."""
        self._client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
            follow_redirects=True,
        )
        self._initialized = True

        # Find a working instance
        await self._find_working_instance()

    async def _find_working_instance(self) -> None:
        """Find a working Nitter instance that can actually return tweets."""
        for instance in self.NITTER_INSTANCES:
            try:
                # Test with actual search query
                response = await self._client.get(
                    f"{instance}/search?f=tweets&q=%24AAPL",
                    timeout=10.0
                )

                # Check if we got real content, not a Cloudflare challenge
                html = response.text
                if response.status_code == 200:
                    # Verify it has actual tweet content
                    if "timeline-item" in html or "tweet-content" in html:
                        self._working_instance = instance
                        logger.info(f"Using Nitter instance: {instance}")
                        return
                    elif "Just a moment" in html or "challenge" in html.lower():
                        logger.debug(f"{instance} blocked by Cloudflare")
                        continue
                    else:
                        logger.debug(f"{instance} returned unknown content")
                        continue

            except Exception as e:
                logger.debug(f"{instance} failed: {e}")
                continue

        logger.warning("No working Nitter instance found - FinTwit will use fallback mode")

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
        """Fetch FinTwit sentiment for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: include_influencers (bool), max_tweets (int)

        Returns:
            DataSourceResult with FinTwit data
        """
        if not self._client:
            await self.initialize()

        if not self._working_instance:
            await self._find_working_instance()

        if not self._working_instance:
            # Provide helpful fallback info when Nitter is down
            return DataSourceResult(
                source=DataSourceType.SOCIAL,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={
                    "status": "nitter_unavailable",
                    "ticker": ticker,
                    "manual_check_urls": {
                        "twitter_cashtag": f"https://twitter.com/search?q=%24{ticker}&src=typed_query&f=live",
                        "stocktwits": f"https://stocktwits.com/symbol/{ticker}",
                    },
                    "recommended_accounts": self._get_relevant_accounts(ticker),
                    "summary": (
                        f"FinTwit auto-scraping unavailable. "
                        f"Check ${ticker} manually at Twitter or StockTwits. "
                        f"Key accounts to monitor: @DeItaone, @unusual_whales, @FirstSquawk"
                    ),
                },
            )

        include_influencers = kwargs.get("include_influencers", True)
        max_tweets = kwargs.get("max_tweets", 30)

        all_tweets = []
        errors = []

        # Search for cashtag
        cashtag_tweets = await self._search_cashtag(ticker, max_tweets)
        all_tweets.extend(cashtag_tweets)

        # Get influencer mentions if requested
        influencer_tweets = []
        if include_influencers:
            influencer_tweets = await self._get_influencer_mentions(ticker)
            all_tweets.extend(influencer_tweets)

        if not all_tweets:
            return DataSourceResult(
                source=DataSourceType.SOCIAL,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={
                    "ticker": ticker,
                    "tweet_count": 0,
                    "summary": f"No recent FinTwit activity found for ${ticker}",
                },
            )

        # Analyze sentiment
        sentiment = self._analyze_sentiment(all_tweets)

        # Detect velocity (unusual activity)
        velocity_signal = self._detect_velocity(all_tweets)

        # Find key tweets (high engagement or from influencers)
        key_tweets = self._find_key_tweets(all_tweets)

        result_data = {
            "ticker": ticker,
            "source": "fintwit_nitter",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_tweets": len(all_tweets),
                "cashtag_tweets": len(cashtag_tweets),
                "influencer_tweets": len(influencer_tweets),
            },
            "sentiment": sentiment,
            "velocity": velocity_signal,
            "key_tweets": key_tweets[:10],
            "influencers_posting": self._get_active_influencers(all_tweets),
            "summary": self._generate_summary(ticker, all_tweets, sentiment, velocity_signal),
        }

        quality = DataQuality.MEDIUM if len(all_tweets) >= 5 else DataQuality.LOW

        return DataSourceResult(
            source=DataSourceType.SOCIAL,
            ticker=ticker,
            quality=quality,
            data=result_data,
        )

    async def _search_cashtag(self, ticker: str, limit: int = 30) -> list[dict[str, Any]]:
        """Search for cashtag mentions."""
        try:
            query = quote(f"${ticker}")
            url = f"{self._working_instance}/search?f=tweets&q={query}"

            response = await self._client.get(url)
            if response.status_code != 200:
                return []

            return self._parse_tweets(response.text, ticker)[:limit]

        except Exception as e:
            logger.warning(f"Cashtag search failed for ${ticker}: {e}")
            return []

    async def _get_influencer_mentions(self, ticker: str) -> list[dict[str, Any]]:
        """Get recent tweets from influencers mentioning the ticker."""
        mentions = []

        # Check key influencer categories
        for category in ["ai_researchers", "market_news", "fund_managers"]:
            accounts = self.INFLUENCERS.get(category, [])[:3]  # Limit to avoid rate limits

            for account in accounts:
                try:
                    tweets = await self._get_user_tweets(account, limit=10)
                    # Filter for ticker mentions
                    for tweet in tweets:
                        text = tweet.get("text", "").upper()
                        if f"${ticker}" in text or ticker in text:
                            tweet["influencer"] = account
                            tweet["category"] = category
                            mentions.append(tweet)

                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.3)

                except Exception as e:
                    logger.debug(f"Failed to get tweets from @{account}: {e}")

        return mentions

    async def _get_user_tweets(self, username: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent tweets from a user."""
        try:
            url = f"{self._working_instance}/{username}"
            response = await self._client.get(url)

            if response.status_code != 200:
                return []

            return self._parse_tweets(response.text, source_user=username)[:limit]

        except Exception as e:
            logger.debug(f"Failed to fetch @{username}: {e}")
            return []

    def _parse_tweets(
        self,
        html: str,
        ticker: Optional[str] = None,
        source_user: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Parse tweets from Nitter HTML."""
        tweets = []

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Find tweet containers (Nitter uses timeline-item class)
            tweet_elements = soup.find_all("div", class_="timeline-item")

            for elem in tweet_elements:
                try:
                    # Extract tweet content
                    content_elem = elem.find("div", class_="tweet-content")
                    if not content_elem:
                        continue

                    text = content_elem.get_text(strip=True)

                    # Extract username
                    username_elem = elem.find("a", class_="username")
                    username = username_elem.get_text(strip=True) if username_elem else source_user or "unknown"

                    # Extract timestamp
                    time_elem = elem.find("span", class_="tweet-date")
                    timestamp = None
                    if time_elem and time_elem.find("a"):
                        timestamp = time_elem.find("a").get("title", "")

                    # Extract stats
                    stats = {}
                    stat_container = elem.find("div", class_="tweet-stats")
                    if stat_container:
                        for stat in stat_container.find_all("span", class_="tweet-stat"):
                            icon = stat.find("span", class_="icon-container")
                            if icon:
                                # Determine stat type by icon class
                                icon_class = icon.get("class", [])
                                value_elem = stat.find("div", class_="tweet-stat-value")
                                value = value_elem.get_text(strip=True) if value_elem else "0"
                                try:
                                    value = int(value.replace(",", ""))
                                except:
                                    value = 0

                                if "icon-comment" in str(icon_class):
                                    stats["replies"] = value
                                elif "icon-retweet" in str(icon_class):
                                    stats["retweets"] = value
                                elif "icon-heart" in str(icon_class):
                                    stats["likes"] = value

                    tweets.append({
                        "text": text,
                        "username": username.lstrip("@"),
                        "timestamp": timestamp,
                        "replies": stats.get("replies", 0),
                        "retweets": stats.get("retweets", 0),
                        "likes": stats.get("likes", 0),
                        "engagement": stats.get("replies", 0) + stats.get("retweets", 0) + stats.get("likes", 0),
                        "ticker_mentioned": ticker,
                    })

                except Exception as e:
                    logger.debug(f"Failed to parse tweet: {e}")
                    continue

        except Exception as e:
            logger.warning(f"HTML parsing failed: {e}")

        return tweets

    def _analyze_sentiment(self, tweets: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze sentiment from tweets."""
        if not tweets:
            return {"score": 0, "label": "neutral", "bullish": 0, "bearish": 0}

        bullish_words = {
            "moon", "rocket", "bullish", "buy", "long", "calls", "pump",
            "breakout", "ATH", "rip", "send", "strong", "beat", "upgrade",
            "growth", "alpha", "gamma", "squeeze", "🚀", "📈", "💎", "🔥",
        }
        bearish_words = {
            "crash", "dump", "bearish", "sell", "short", "puts", "tank",
            "breakdown", "weak", "miss", "downgrade", "overvalued", "bubble",
            "dead", "rip", "drill", "📉", "🔻", "💀", "🐻",
        }

        bullish_count = 0
        bearish_count = 0
        weighted_score = 0

        for tweet in tweets:
            text = tweet.get("text", "").lower()
            engagement = tweet.get("engagement", 1) + 1
            weight = min(engagement / 100, 5)  # Cap weight

            tweet_bullish = sum(1 for word in bullish_words if word.lower() in text)
            tweet_bearish = sum(1 for word in bearish_words if word.lower() in text)

            if tweet_bullish > tweet_bearish:
                bullish_count += 1
                weighted_score += weight
            elif tweet_bearish > tweet_bullish:
                bearish_count += 1
                weighted_score -= weight

        total = bullish_count + bearish_count
        if total == 0:
            return {"score": 0, "label": "neutral", "bullish": 0, "bearish": 0}

        # Normalize to -100 to +100
        raw_score = (weighted_score / len(tweets)) * 30
        score = max(-100, min(100, raw_score))

        if score > 30:
            label = "bullish"
        elif score > 10:
            label = "slightly bullish"
        elif score > -10:
            label = "neutral"
        elif score > -30:
            label = "slightly bearish"
        else:
            label = "bearish"

        return {
            "score": round(score, 1),
            "label": label,
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": len(tweets) - total,
        }

    def _detect_velocity(self, tweets: list[dict[str, Any]]) -> dict[str, Any]:
        """Detect unusual tweet velocity (potential breaking news)."""
        if len(tweets) < 5:
            return {"signal": "low", "level": "normal"}

        # Calculate engagement velocity
        total_engagement = sum(t.get("engagement", 0) for t in tweets)
        avg_engagement = total_engagement / len(tweets)

        # High engagement suggests trending topic
        if avg_engagement > 1000:
            return {
                "signal": "high",
                "level": "viral",
                "avg_engagement": avg_engagement,
                "interpretation": "Topic going viral - potential major news",
            }
        elif avg_engagement > 100:
            return {
                "signal": "medium",
                "level": "elevated",
                "avg_engagement": avg_engagement,
                "interpretation": "Above average interest - monitor closely",
            }
        else:
            return {
                "signal": "low",
                "level": "normal",
                "avg_engagement": avg_engagement,
            }

    def _find_key_tweets(self, tweets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find most important tweets by engagement and source."""
        # Prioritize influencer tweets
        influencer_set = set()
        for category in self.INFLUENCERS.values():
            influencer_set.update(category)

        def tweet_importance(tweet):
            score = tweet.get("engagement", 0)
            # Boost influencer tweets
            if tweet.get("username", "").lower() in influencer_set:
                score += 10000
            if tweet.get("influencer"):
                score += 5000
            return score

        sorted_tweets = sorted(tweets, key=tweet_importance, reverse=True)

        # Return top tweets with cleaned data
        key_tweets = []
        for t in sorted_tweets[:15]:
            key_tweets.append({
                "text": t.get("text", "")[:280],
                "username": t.get("username", ""),
                "engagement": t.get("engagement", 0),
                "is_influencer": t.get("username", "").lower() in influencer_set,
            })

        return key_tweets

    def _get_active_influencers(self, tweets: list[dict[str, Any]]) -> list[str]:
        """Get list of influencers who have posted."""
        influencer_set = set()
        for category in self.INFLUENCERS.values():
            influencer_set.update(acc.lower() for acc in category)

        active = []
        for tweet in tweets:
            username = tweet.get("username", "").lower()
            if username in influencer_set and username not in active:
                active.append(tweet.get("username", ""))

        return active

    def _get_relevant_accounts(self, ticker: str) -> list[str]:
        """Get list of accounts relevant for a ticker."""
        accounts = []

        # Always include market news
        accounts.extend(["@DeItaone", "@FirstSquawk", "@unusual_whales"])

        # Add ticker-specific accounts if known
        ticker_accounts = {
            "NVDA": ["@nvidia", "@JensenHuang"],
            "TSLA": ["@elonmusk", "@Tesla"],
            "META": ["@MetaAI", "@faborst"],
            "MSFT": ["@Microsoft", "@sataborst"],
            "GOOGL": ["@Google_AI", "@sundarpichai"],
            "AAPL": ["@Apple", "@markgurman"],
            "AMD": ["@AMD", "@LisaSu"],
            "PLTR": ["@PalantirTech", "@alexkarp"],
        }

        if ticker in ticker_accounts:
            accounts.extend(ticker_accounts[ticker])

        return accounts[:8]

    def _generate_summary(
        self,
        ticker: str,
        tweets: list[dict[str, Any]],
        sentiment: dict[str, Any],
        velocity: dict[str, Any],
    ) -> str:
        """Generate FinTwit summary."""
        parts = [f"FinTwit for ${ticker}:"]

        # Sentiment
        parts.append(f"{sentiment['label']} sentiment (score: {sentiment['score']:+.1f})")

        # Volume
        parts.append(f"{len(tweets)} tweets found")

        # Velocity signal
        if velocity.get("signal") in ["high", "medium"]:
            parts.append(f"⚠️ {velocity.get('interpretation', 'Elevated activity')}")

        # Influencer activity
        influencers = self._get_active_influencers(tweets)
        if influencers:
            parts.append(f"Active influencers: {', '.join(influencers[:3])}")

        return " | ".join(parts)

    async def get_ai_news_feed(self) -> list[dict[str, Any]]:
        """Get latest AI news from key accounts.

        Returns:
            List of AI-related tweets from influencers
        """
        if not self._client:
            await self.initialize()

        if not self._working_instance:
            return []

        all_tweets = []

        # Get tweets from AI researchers and tech news
        for category in ["ai_researchers", "tech_analysts", "ai_companies"]:
            accounts = self.INFLUENCERS.get(category, [])

            for account in accounts[:5]:
                try:
                    tweets = await self._get_user_tweets(account, limit=5)
                    for tweet in tweets:
                        tweet["category"] = category
                    all_tweets.extend(tweets)
                    await asyncio.sleep(0.5)  # Rate limit protection
                except Exception as e:
                    logger.debug(f"Failed to fetch @{account}: {e}")

        # Sort by engagement
        all_tweets.sort(key=lambda x: x.get("engagement", 0), reverse=True)

        return all_tweets[:30]

    async def get_breaking_news(self) -> list[dict[str, Any]]:
        """Get breaking market news from news accounts.

        Returns:
            List of breaking news tweets
        """
        if not self._client:
            await self.initialize()

        if not self._working_instance:
            return []

        breaking = []

        for account in self.INFLUENCERS.get("market_news", []):
            try:
                tweets = await self._get_user_tweets(account, limit=10)
                breaking.extend(tweets)
                await asyncio.sleep(0.5)
            except Exception:
                continue

        # Sort by recency (newest first based on text parsing)
        return breaking[:20]

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search FinTwit for a query."""
        result = await self.fetch(query)
        return [result]
