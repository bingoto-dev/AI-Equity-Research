"""Base class and models for data sources."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DataSourceType(Enum):
    """Types of data sources."""

    # Original sources
    SEC_EDGAR = "sec_edgar"
    YAHOO_FINANCE = "yahoo_finance"
    NEWS_API = "news_api"
    ALPHA_VANTAGE = "alpha_vantage"
    WEB_SEARCH = "web_search"
    TWITTER = "twitter"

    # New sources - Social sentiment
    SOCIAL = "social"  # StockTwits, Reddit

    # New sources - Alternative data
    ALTERNATIVE = "alternative"  # GitHub, job postings

    # New sources - Regulatory
    REGULATORY = "regulatory"  # SEC insider trading

    # New sources - Economic
    ECONOMIC = "economic"  # FRED macro data

    # New sources - News
    NEWS = "news"  # RSS aggregator

    # New sources - Fundamental
    FUNDAMENTAL = "fundamental"  # Earnings calendar


class DataQuality(Enum):
    """Data quality indicators."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FinancialData(BaseModel):
    """Financial metrics for a company."""

    ticker: str
    company_name: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    avg_volume: Optional[float] = None
    shares_outstanding: Optional[float] = None


class PriceData(BaseModel):
    """Price and technical data."""

    ticker: str
    current_price: float
    previous_close: float
    open_price: float
    day_high: float
    day_low: float
    volume: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Moving averages
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_20: Optional[float] = None

    # Technical indicators
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None

    # Relative performance
    change_1d: Optional[float] = None
    change_5d: Optional[float] = None
    change_1m: Optional[float] = None
    change_3m: Optional[float] = None
    change_ytd: Optional[float] = None
    change_1y: Optional[float] = None

    # Volume analysis
    volume_sma_20: Optional[float] = None
    relative_volume: Optional[float] = None


class NewsArticle(BaseModel):
    """A news article about a company."""

    ticker: Optional[str] = None
    title: str
    description: Optional[str] = None
    summary: Optional[str] = None  # Alias for description
    content: Optional[str] = None
    url: str
    source: str
    published_at: Optional[datetime] = None
    sentiment: Optional[float] = Field(None, ge=-1, le=1, description="Sentiment score -1 to 1")
    relevance: Optional[float] = Field(None, ge=0, le=1, description="Relevance score 0 to 1")


class SECFiling(BaseModel):
    """An SEC filing."""

    ticker: str
    company_name: str
    form_type: str  # 10-K, 10-Q, 8-K, etc.
    filing_date: datetime
    accepted_date: Optional[datetime] = None
    accession_number: str
    file_url: str
    description: Optional[str] = None
    summary: Optional[str] = None  # LLM-generated summary


class CompanyProfile(BaseModel):
    """Company profile information."""

    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    headquarters: Optional[str] = None
    ceo: Optional[str] = None
    founded: Optional[int] = None
    exchange: Optional[str] = None


class InsiderTransaction(BaseModel):
    """Insider trading transaction."""

    ticker: str
    insider_name: str
    title: Optional[str] = None
    transaction_type: str  # Buy, Sell, etc.
    shares: int
    price: Optional[float] = None
    value: Optional[float] = None
    transaction_date: datetime
    filing_date: datetime


class InstitutionalHolding(BaseModel):
    """Institutional holding information."""

    ticker: str
    institution_name: str
    shares: int
    value: float
    percent_outstanding: float
    change_shares: Optional[int] = None
    change_percent: Optional[float] = None
    report_date: datetime


class DataSourceResult(BaseModel):
    """Result from a data source query."""

    source: DataSourceType
    ticker: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    quality: DataQuality = DataQuality.UNKNOWN
    data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    # Structured data fields
    financial_data: Optional[FinancialData] = None
    price_data: Optional[PriceData] = None
    news: list[NewsArticle] = Field(default_factory=list)
    filings: list[SECFiling] = Field(default_factory=list)
    profile: Optional[CompanyProfile] = None
    insider_transactions: list[InsiderTransaction] = Field(default_factory=list)
    institutional_holdings: list[InstitutionalHolding] = Field(default_factory=list)


class BaseDataSource(ABC):
    """Abstract base class for data sources."""

    def __init__(self, source_type: DataSourceType):
        """Initialize the data source.

        Args:
            source_type: Type identifier for this source
        """
        self.source_type = source_type
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the data source (e.g., authenticate, setup connections)."""
        pass

    @abstractmethod
    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch data for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters for the query

        Returns:
            DataSourceResult containing the fetched data
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search for data matching a query.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of matching results
        """
        pass

    async def health_check(self) -> bool:
        """Check if the data source is available.

        Returns:
            True if healthy, False otherwise
        """
        return self._initialized

    @property
    def is_initialized(self) -> bool:
        """Check if the data source has been initialized."""
        return self._initialized

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False
