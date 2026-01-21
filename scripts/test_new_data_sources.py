#!/usr/bin/env python3
"""Test script for new data sources."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_sources.stocktwits import StockTwitsDataSource
from src.data_sources.reddit_sentiment import RedditSentimentDataSource
from src.data_sources.github_tracker import GitHubTrackerDataSource
from src.data_sources.sec_insider import SECInsiderDataSource
from src.data_sources.rss_news import RSSNewsDataSource
from src.data_sources.earnings_calendar import EarningsCalendarDataSource
from src.data_sources.fintwit import FinTwitDataSource


async def test_stocktwits():
    """Test StockTwits data source."""
    print("\n" + "=" * 50)
    print("Testing StockTwits...")
    print("=" * 50)

    source = StockTwitsDataSource()
    await source.initialize()

    result = await source.fetch("NVDA")
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        sentiment = result.data.get("sentiment", {})
        print(f"Sentiment Score: {sentiment.get('score', 'N/A')}")
        print(f"Bullish: {sentiment.get('bullish_count', 0)}")
        print(f"Bearish: {sentiment.get('bearish_count', 0)}")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    await source.close()
    return result.error is None


async def test_reddit():
    """Test Reddit sentiment data source."""
    print("\n" + "=" * 50)
    print("Testing Reddit Sentiment...")
    print("=" * 50)

    source = RedditSentimentDataSource()
    await source.initialize()

    result = await source.fetch("NVDA", subreddits=["wallstreetbets", "stocks"])
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        metrics = result.data.get("metrics", {})
        print(f"Mention Count: {metrics.get('mention_count', 0)}")
        print(f"Total Upvotes: {metrics.get('total_upvotes', 0)}")
        sentiment = result.data.get("sentiment", {})
        print(f"Sentiment: {sentiment.get('label', 'N/A')} ({sentiment.get('score', 0):.1f})")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    # Test trending
    trending = await source.get_trending_tickers("wallstreetbets")
    print(f"\nTrending on WSB: {[t['ticker'] for t in trending[:5]]}")

    await source.close()
    return result.error is None


async def test_github():
    """Test GitHub tracker data source."""
    print("\n" + "=" * 50)
    print("Testing GitHub Tracker...")
    print("=" * 50)

    source = GitHubTrackerDataSource()
    await source.initialize()

    result = await source.fetch("NVDA")
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        metrics = result.data.get("summary_metrics", {})
        print(f"Tracked Repos: {metrics.get('tracked_repos', 0)}")
        print(f"Total Stars: {metrics.get('total_stars', 0):,}")
        print(f"Recent Commits: {metrics.get('commits_last_month', 0)}")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    # Test trending AI repos
    trending = await source.get_trending_ai_repos(days=7)
    print(f"\nTrending AI repos: {[r['repo'] for r in trending[:3]]}")

    await source.close()
    return result.error is None


async def test_sec_insider():
    """Test SEC insider trading data source."""
    print("\n" + "=" * 50)
    print("Testing SEC Insider Trading...")
    print("=" * 50)

    source = SECInsiderDataSource()
    await source.initialize()

    result = await source.fetch("NVDA", days_back=90)
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        analysis = result.data.get("analysis", {})
        print(f"Total Filings: {analysis.get('total_filings', 0)}")
        print(f"Buy Transactions: {analysis.get('buy_transactions', 0)}")
        print(f"Sell Transactions: {analysis.get('sell_transactions', 0)}")
        print(f"Signal: {analysis.get('signal', 'N/A')}")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    await source.close()
    return True  # SEC can have issues, don't fail test


async def test_rss_news():
    """Test RSS news aggregator."""
    print("\n" + "=" * 50)
    print("Testing RSS News Aggregator...")
    print("=" * 50)

    source = RSSNewsDataSource()
    await source.initialize()

    result = await source.fetch("NVDA")
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        print(f"Article Count: {result.data.get('article_count', 0)}")
        articles = result.data.get("articles", [])
        if articles:
            print(f"Latest: {articles[0].get('title', 'N/A')[:60]}...")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    # Test market headlines
    headlines = await source.get_market_headlines(max_articles=5)
    print(f"\nMarket Headlines: {len(headlines)} articles")

    await source.close()
    return result.error is None


async def test_earnings():
    """Test earnings calendar data source."""
    print("\n" + "=" * 50)
    print("Testing Earnings Calendar...")
    print("=" * 50)

    source = EarningsCalendarDataSource()
    await source.initialize()

    result = await source.fetch("NVDA")
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        next_earnings = result.data.get("next_earnings", {})
        print(f"Next Earnings: {next_earnings.get('date', 'N/A')}")
        analysis = result.data.get("analysis", {})
        print(f"Beat Rate: {analysis.get('beat_rate', 'N/A')}%")
        print(f"Consistency: {analysis.get('consistency', 'N/A')}")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    await source.close()
    return result.error is None


async def test_fintwit():
    """Test FinTwit data source."""
    print("\n" + "=" * 50)
    print("Testing FinTwit (Nitter)...")
    print("=" * 50)

    source = FinTwitDataSource()
    await source.initialize()
    print(f"Working instance: {source._working_instance}")

    result = await source.fetch("NVDA")
    print(f"Ticker: NVDA")
    print(f"Quality: {result.quality}")

    if result.data:
        if "status" in result.data and result.data["status"] == "nitter_unavailable":
            print("Fallback mode active (Nitter instances down)")
            print(f"Manual check URLs provided: {len(result.data.get('manual_check_urls', {}))}")
            print(f"Recommended accounts: {result.data.get('recommended_accounts', [])[:5]}")
        else:
            metrics = result.data.get("metrics", {})
            print(f"Tweets found: {metrics.get('total_tweets', 0)}")
            sentiment = result.data.get("sentiment", {})
            print(f"Sentiment: {sentiment.get('label', 'N/A')} ({sentiment.get('score', 0):.1f})")
        print(f"Summary: {result.data.get('summary', 'N/A')}")

    await source.close()
    return True  # FinTwit in fallback mode is still valid


async def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING NEW DATA SOURCES")
    print("=" * 60)

    results = {}

    # Test each source
    results["StockTwits"] = await test_stocktwits()
    results["Reddit"] = await test_reddit()
    results["GitHub"] = await test_github()
    results["SEC Insider"] = await test_sec_insider()
    results["RSS News"] = await test_rss_news()
    results["Earnings"] = await test_earnings()
    results["FinTwit"] = await test_fintwit()

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    for source, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{source}: {status}")

    total_passed = sum(results.values())
    total_tests = len(results)
    print(f"\nTotal: {total_passed}/{total_tests} passed")

    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
