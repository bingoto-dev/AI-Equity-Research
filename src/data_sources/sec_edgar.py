"""SEC EDGAR data source for company filings."""

import asyncio
from datetime import datetime
from typing import Any, Optional

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
    SECFiling,
)


class SECEdgarDataSource(BaseDataSource):
    """SEC EDGAR data source for 10-K, 10-Q, 8-K filings."""

    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = f"{BASE_URL}/submissions"
    FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

    def __init__(self, user_agent: str):
        """Initialize SEC EDGAR data source.

        Args:
            user_agent: Required user agent string for SEC API
        """
        super().__init__(DataSourceType.SEC_EDGAR)
        self.user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None
        self._cik_cache: dict[str, str] = {}

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        self._initialized = True

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def _get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK number for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            CIK number or None if not found
        """
        if ticker.upper() in self._cik_cache:
            return self._cik_cache[ticker.upper()]

        try:
            # SEC ticker to CIK mapping
            url = f"{self.BASE_URL}/files/company_tickers.json"
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()

            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry.get("cik_str", "")).zfill(10)
                    self._cik_cache[ticker.upper()] = cik
                    return cik

            return None
        except Exception:
            return None

    async def fetch(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> DataSourceResult:
        """Fetch SEC filings for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: Additional parameters (form_types, limit)

        Returns:
            DataSourceResult with SEC filings
        """
        if not self._client:
            await self.initialize()

        form_types = kwargs.get("form_types", ["10-K", "10-Q", "8-K"])
        limit = kwargs.get("limit", 10)

        try:
            cik = await self._get_cik(ticker)
            if not cik:
                return DataSourceResult(
                    source=DataSourceType.SEC_EDGAR,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    error=f"CIK not found for ticker {ticker}",
                )

            # Get company submissions
            url = f"{self.SUBMISSIONS_URL}/CIK{cik}.json"
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()

            company_name = data.get("name", ticker)
            filings_data = data.get("filings", {}).get("recent", {})

            filings = []
            form_list = filings_data.get("form", [])
            filing_date_list = filings_data.get("filingDate", [])
            accession_list = filings_data.get("accessionNumber", [])
            primary_doc_list = filings_data.get("primaryDocument", [])

            count = 0
            for i, form in enumerate(form_list):
                if form in form_types and count < limit:
                    accession = accession_list[i].replace("-", "")
                    primary_doc = primary_doc_list[i]
                    file_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{primary_doc}"

                    filing = SECFiling(
                        ticker=ticker,
                        company_name=company_name,
                        form_type=form,
                        filing_date=datetime.strptime(filing_date_list[i], "%Y-%m-%d"),
                        accession_number=accession_list[i],
                        file_url=file_url,
                    )
                    filings.append(filing)
                    count += 1

            return DataSourceResult(
                source=DataSourceType.SEC_EDGAR,
                ticker=ticker,
                quality=DataQuality.HIGH,
                filings=filings,
                data={
                    "company_name": company_name,
                    "cik": cik,
                    "total_filings": len(form_list),
                },
            )

        except Exception as e:
            return DataSourceResult(
                source=DataSourceType.SEC_EDGAR,
                ticker=ticker,
                quality=DataQuality.LOW,
                error=str(e),
            )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search for companies by name.

        Args:
            query: Company name search query
            **kwargs: Additional parameters

        Returns:
            List of matching results
        """
        if not self._client:
            await self.initialize()

        results = []
        try:
            url = f"{self.BASE_URL}/files/company_tickers.json"
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()

            query_lower = query.lower()
            matches = []
            for entry in data.values():
                title = entry.get("title", "").lower()
                if query_lower in title:
                    matches.append(entry.get("ticker"))

            # Fetch data for top matches
            for ticker in matches[:5]:
                result = await self.fetch(ticker)
                results.append(result)

        except Exception:
            pass

        return results

    async def get_filing_content(self, file_url: str) -> Optional[str]:
        """Get the content of a specific filing.

        Args:
            file_url: URL to the filing document

        Returns:
            Filing content as text or None
        """
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get(file_url)
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    async def get_recent_8k(self, ticker: str, limit: int = 5) -> list[SECFiling]:
        """Get recent 8-K filings (material events).

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of filings

        Returns:
            List of 8-K filings
        """
        result = await self.fetch(ticker, form_types=["8-K"], limit=limit)
        return result.filings
