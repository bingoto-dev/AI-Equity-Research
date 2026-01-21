"""GitHub API data source for tracking AI/ML repository trends."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
)

logger = logging.getLogger(__name__)


class GitHubTrackerDataSource(BaseDataSource):
    """GitHub API for tracking AI/ML technology adoption trends.

    Monitors repository activity for key AI frameworks and tools.
    Free tier: 60 requests/hour unauthenticated, 5000/hour with token.
    """

    BASE_URL = "https://api.github.com"

    # Key AI/ML repositories to track (owner/repo -> associated companies)
    TRACKED_REPOS = {
        # NVIDIA ecosystem
        "NVIDIA/TensorRT": "NVDA",
        "NVIDIA/cuda-samples": "NVDA",
        "NVIDIA/NeMo": "NVDA",
        "NVIDIA/Megatron-LM": "NVDA",

        # Microsoft/OpenAI
        "microsoft/DeepSpeed": "MSFT",
        "microsoft/onnxruntime": "MSFT",
        "Azure/azure-sdk-for-python": "MSFT",

        # Meta
        "facebookresearch/llama": "META",
        "pytorch/pytorch": "META",
        "facebookresearch/faiss": "META",

        # Google
        "google/jax": "GOOGL",
        "tensorflow/tensorflow": "GOOGL",
        "google/gemma.cpp": "GOOGL",

        # Amazon
        "aws/sagemaker-python-sdk": "AMZN",
        "aws/amazon-braket-sdk-python": "AMZN",

        # AMD
        "ROCm/ROCm": "AMD",

        # Other AI companies
        "anthropics/anthropic-sdk-python": "PRIVATE:Anthropic",
        "openai/openai-python": "MSFT",  # OpenAI -> MSFT investment
        "huggingface/transformers": "PRIVATE:HuggingFace",
        "langchain-ai/langchain": "PRIVATE:LangChain",
        "run-llama/llama_index": "PRIVATE:LlamaIndex",
    }

    # AI/ML topics to search for trending repos
    AI_TOPICS = [
        "machine-learning",
        "deep-learning",
        "llm",
        "large-language-models",
        "transformers",
        "generative-ai",
        "ai",
        "neural-network",
    ]

    def __init__(self, token: Optional[str] = None):
        """Initialize GitHub tracker.

        Args:
            token: Optional GitHub personal access token for higher rate limits
        """
        super().__init__(DataSourceType.ALTERNATIVE)
        self._client: Optional[httpx.AsyncClient] = None
        self._token = token

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Equity-Research/1.0",
        }
        if self._token:
            headers["Authorization"] = f"token {self._token}"

        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
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
        """Fetch GitHub activity for repos associated with a company.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters

        Returns:
            DataSourceResult with GitHub activity data
        """
        if not self._client:
            await self.initialize()

        # Find repos associated with this ticker
        relevant_repos = [
            repo for repo, company in self.TRACKED_REPOS.items()
            if company == ticker
        ]

        if not relevant_repos:
            return DataSourceResult(
                source=DataSourceType.ALTERNATIVE,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={
                    "ticker": ticker,
                    "tracked_repos": 0,
                    "summary": f"No tracked GitHub repositories for {ticker}",
                },
            )

        repo_stats = []
        total_stars = 0
        total_forks = 0
        recent_commits = 0

        for repo in relevant_repos:
            try:
                stats = await self._get_repo_stats(repo)
                if stats:
                    repo_stats.append(stats)
                    total_stars += stats.get("stars", 0)
                    total_forks += stats.get("forks", 0)
                    recent_commits += stats.get("commits_last_month", 0)
            except Exception as e:
                logger.warning(f"Failed to fetch stats for {repo}: {e}")

        if not repo_stats:
            return DataSourceResult(
                source=DataSourceType.ALTERNATIVE,
                ticker=ticker,
                quality=DataQuality.LOW,
                data={"ticker": ticker, "error": "Failed to fetch repo stats"},
            )

        result_data = {
            "ticker": ticker,
            "source": "github",
            "timestamp": datetime.utcnow().isoformat(),
            "summary_metrics": {
                "tracked_repos": len(repo_stats),
                "total_stars": total_stars,
                "total_forks": total_forks,
                "commits_last_month": recent_commits,
            },
            "repositories": repo_stats,
            "summary": self._generate_summary(ticker, repo_stats, total_stars, recent_commits),
        }

        return DataSourceResult(
            source=DataSourceType.ALTERNATIVE,
            ticker=ticker,
            quality=DataQuality.MEDIUM,
            data=result_data,
        )

    async def _get_repo_stats(self, repo: str) -> Optional[dict[str, Any]]:
        """Get statistics for a single repository."""
        # Get repo info
        response = await self._client.get(f"{self.BASE_URL}/repos/{repo}")
        if response.status_code != 200:
            return None

        data = response.json()

        # Get recent commit activity
        since = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
        commits_response = await self._client.get(
            f"{self.BASE_URL}/repos/{repo}/commits",
            params={"since": since, "per_page": 100}
        )
        commit_count = len(commits_response.json()) if commits_response.status_code == 200 else 0

        return {
            "repo": repo,
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "watchers": data.get("subscribers_count", 0),
            "language": data.get("language"),
            "updated_at": data.get("updated_at"),
            "commits_last_month": commit_count,
            "description": data.get("description", "")[:200],
        }

    async def get_trending_ai_repos(self, days: int = 7) -> list[dict[str, Any]]:
        """Get trending AI/ML repositories created or updated recently.

        Args:
            days: Look back period

        Returns:
            List of trending repos with metadata
        """
        if not self._client:
            await self.initialize()

        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        trending = []

        for topic in self.AI_TOPICS[:3]:  # Limit to avoid rate limits
            try:
                response = await self._client.get(
                    f"{self.BASE_URL}/search/repositories",
                    params={
                        "q": f"topic:{topic} pushed:>{since}",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 10,
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("items", []):
                        trending.append({
                            "repo": item.get("full_name"),
                            "description": item.get("description", "")[:200],
                            "stars": item.get("stargazers_count", 0),
                            "forks": item.get("forks_count", 0),
                            "language": item.get("language"),
                            "topic": topic,
                            "url": item.get("html_url"),
                        })

            except Exception as e:
                logger.warning(f"Failed to search topic {topic}: {e}")

        # Dedupe by repo name and sort by stars
        seen = set()
        unique_trending = []
        for repo in trending:
            if repo["repo"] not in seen:
                seen.add(repo["repo"])
                unique_trending.append(repo)

        unique_trending.sort(key=lambda x: x["stars"], reverse=True)
        return unique_trending[:20]

    async def get_framework_adoption(self) -> dict[str, Any]:
        """Compare adoption metrics across major AI frameworks.

        Returns:
            Comparison data for major frameworks
        """
        if not self._client:
            await self.initialize()

        frameworks = {
            "pytorch": ("pytorch/pytorch", "META"),
            "tensorflow": ("tensorflow/tensorflow", "GOOGL"),
            "jax": ("google/jax", "GOOGL"),
            "transformers": ("huggingface/transformers", "PRIVATE:HuggingFace"),
            "langchain": ("langchain-ai/langchain", "PRIVATE:LangChain"),
        }

        results = {}
        for name, (repo, company) in frameworks.items():
            stats = await self._get_repo_stats(repo)
            if stats:
                stats["associated_company"] = company
                results[name] = stats

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "frameworks": results,
        }

    def _generate_summary(
        self,
        ticker: str,
        repos: list[dict[str, Any]],
        total_stars: int,
        recent_commits: int,
    ) -> str:
        """Generate summary of GitHub activity."""
        top_repo = max(repos, key=lambda x: x.get("stars", 0)) if repos else None
        top_name = top_repo.get("repo", "N/A") if top_repo else "N/A"

        return (
            f"GitHub activity for {ticker}: {len(repos)} tracked repos with "
            f"{total_stars:,} total stars and {recent_commits} commits in last 30 days. "
            f"Most popular: {top_name}."
        )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search GitHub repositories."""
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/search/repositories",
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 10,
                }
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                results.append(DataSourceResult(
                    source=DataSourceType.ALTERNATIVE,
                    quality=DataQuality.MEDIUM,
                    data={
                        "repo": item.get("full_name"),
                        "description": item.get("description"),
                        "stars": item.get("stargazers_count"),
                        "url": item.get("html_url"),
                    },
                ))

            return results

        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return []
