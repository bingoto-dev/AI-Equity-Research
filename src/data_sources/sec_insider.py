"""SEC EDGAR data source for insider trading (Form 4) data."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from xml.etree import ElementTree

import httpx

from src.data_sources.base import (
    BaseDataSource,
    DataQuality,
    DataSourceResult,
    DataSourceType,
)

logger = logging.getLogger(__name__)


class SECInsiderDataSource(BaseDataSource):
    """SEC EDGAR API for insider trading data (Form 4 filings).

    Free API with rate limit of 10 requests/second.
    Requires User-Agent header with contact info.
    """

    BASE_URL = "https://efts.sec.gov/LATEST/search-index"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions"
    FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

    # CIK lookup for major companies (backup if API fails)
    CIK_CACHE = {
        "NVDA": "0001045810",
        "MSFT": "0000789019",
        "AAPL": "0000320193",
        "GOOGL": "0001652044",
        "META": "0001326801",
        "AMZN": "0001018724",
        "TSLA": "0001318605",
        "AMD": "0000002488",
        "INTC": "0000050863",
        "TSM": "0001046179",
    }

    def __init__(self, user_agent: str = "AI-Equity-Research research@example.com"):
        """Initialize SEC insider data source.

        Args:
            user_agent: Required user agent for SEC API
        """
        super().__init__(DataSourceType.REGULATORY)
        self._client: Optional[httpx.AsyncClient] = None
        self._user_agent = user_agent

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": self._user_agent,
                "Accept": "application/json",
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
        """Fetch recent insider trading for a ticker.

        Args:
            ticker: Stock ticker symbol
            **kwargs: days_back (default 90)

        Returns:
            DataSourceResult with insider trading data
        """
        if not self._client:
            await self.initialize()

        days_back = kwargs.get("days_back", 90)

        try:
            # Try to get CIK for the company
            cik = await self._get_cik(ticker)
            if not cik:
                return DataSourceResult(
                    source=DataSourceType.REGULATORY,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    data={"error": f"Could not find CIK for {ticker}"},
                )

            # Get Form 4 filings
            filings = await self._get_form4_filings(cik, ticker, days_back)

            if not filings:
                return DataSourceResult(
                    source=DataSourceType.REGULATORY,
                    ticker=ticker,
                    quality=DataQuality.LOW,
                    data={
                        "ticker": ticker,
                        "cik": cik,
                        "filings_count": 0,
                        "summary": f"No Form 4 filings found for {ticker} in last {days_back} days",
                    },
                )

            # Analyze insider activity
            analysis = self._analyze_insider_activity(filings)

            result_data = {
                "ticker": ticker,
                "cik": cik,
                "source": "sec_edgar",
                "timestamp": datetime.utcnow().isoformat(),
                "period_days": days_back,
                "filings_count": len(filings),
                "analysis": analysis,
                "recent_filings": filings[:15],
                "summary": self._generate_summary(ticker, filings, analysis),
            }

            return DataSourceResult(
                source=DataSourceType.REGULATORY,
                ticker=ticker,
                quality=DataQuality.HIGH,
                data=result_data,
            )

        except Exception as e:
            logger.error(f"SEC insider fetch error for {ticker}: {e}")
            return DataSourceResult(
                source=DataSourceType.REGULATORY,
                ticker=ticker,
                quality=DataQuality.UNKNOWN,
                error=str(e),
            )

    async def _get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK number for a ticker."""
        # Check cache first
        if ticker in self.CIK_CACHE:
            return self.CIK_CACHE[ticker]

        try:
            # Try company tickers JSON
            response = await self._client.get(
                "https://www.sec.gov/files/company_tickers.json"
            )
            if response.status_code == 200:
                data = response.json()
                for entry in data.values():
                    if entry.get("ticker", "").upper() == ticker.upper():
                        cik = str(entry.get("cik_str", "")).zfill(10)
                        self.CIK_CACHE[ticker] = cik
                        return cik
        except Exception as e:
            logger.warning(f"CIK lookup failed for {ticker}: {e}")

        return None

    async def _get_form4_filings(
        self,
        cik: str,
        ticker: str,
        days_back: int,
    ) -> list[dict[str, Any]]:
        """Get Form 4 filings from SEC EDGAR."""
        filings = []

        try:
            # Use full-text search endpoint
            search_url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": f'formType:"4" AND ticker:{ticker}',
                "dateRange": "custom",
                "startdt": (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                "enddt": datetime.now().strftime("%Y-%m-%d"),
                "forms": "4",
            }

            response = await self._client.get(
                f"https://www.sec.gov/cgi-bin/browse-edgar",
                params={
                    "action": "getcompany",
                    "CIK": cik,
                    "type": "4",
                    "dateb": "",
                    "owner": "include",
                    "count": 40,
                    "output": "atom",
                }
            )

            if response.status_code == 200:
                # Parse Atom feed
                filings = self._parse_atom_feed(response.text, ticker)

        except Exception as e:
            logger.warning(f"Form 4 search failed: {e}")

        # Fallback: try submissions API
        if not filings:
            try:
                cik_padded = cik.lstrip("0").zfill(10)
                response = await self._client.get(
                    f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
                )

                if response.status_code == 200:
                    data = response.json()
                    recent_filings = data.get("filings", {}).get("recent", {})

                    forms = recent_filings.get("form", [])
                    dates = recent_filings.get("filingDate", [])
                    accessions = recent_filings.get("accessionNumber", [])
                    descriptions = recent_filings.get("primaryDocument", [])

                    cutoff = datetime.now() - timedelta(days=days_back)

                    for i, form in enumerate(forms):
                        if form == "4" and i < len(dates):
                            filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
                            if filing_date >= cutoff:
                                filings.append({
                                    "form": "4",
                                    "filing_date": dates[i],
                                    "accession": accessions[i] if i < len(accessions) else "",
                                    "document": descriptions[i] if i < len(descriptions) else "",
                                })

            except Exception as e:
                logger.warning(f"Submissions API fallback failed: {e}")

        return filings

    def _parse_atom_feed(self, xml_content: str, ticker: str) -> list[dict[str, Any]]:
        """Parse SEC EDGAR Atom feed for Form 4 filings."""
        filings = []

        try:
            # Remove namespace for easier parsing
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content)
            root = ElementTree.fromstring(xml_content)

            for entry in root.findall(".//entry"):
                title = entry.findtext("title", "")
                updated = entry.findtext("updated", "")
                link = entry.find("link")
                href = link.get("href", "") if link is not None else ""

                # Extract insider name from title
                insider_match = re.search(r"4 - (.+?) \(", title)
                insider_name = insider_match.group(1) if insider_match else "Unknown"

                filings.append({
                    "form": "4",
                    "insider_name": insider_name,
                    "filing_date": updated[:10] if updated else "",
                    "title": title,
                    "link": href,
                })

        except Exception as e:
            logger.warning(f"Atom feed parsing failed: {e}")

        return filings

    def _analyze_insider_activity(self, filings: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze insider trading patterns."""
        buy_count = 0
        sell_count = 0
        unique_insiders = set()

        for filing in filings:
            title = filing.get("title", "").lower()
            insider = filing.get("insider_name", "Unknown")
            unique_insiders.add(insider)

            # Simplified buy/sell detection from titles
            if "acquisition" in title or "buy" in title:
                buy_count += 1
            elif "disposition" in title or "sell" in title or "sale" in title:
                sell_count += 1

        total = buy_count + sell_count
        buy_sell_ratio = buy_count / sell_count if sell_count > 0 else float('inf') if buy_count > 0 else 0

        # Determine signal
        if buy_sell_ratio > 2:
            signal = "strong_buy"
        elif buy_sell_ratio > 1:
            signal = "moderate_buy"
        elif buy_sell_ratio > 0.5:
            signal = "neutral"
        elif buy_sell_ratio > 0:
            signal = "moderate_sell"
        else:
            signal = "strong_sell" if sell_count > 5 else "neutral"

        return {
            "total_filings": len(filings),
            "buy_transactions": buy_count,
            "sell_transactions": sell_count,
            "buy_sell_ratio": round(buy_sell_ratio, 2) if buy_sell_ratio != float('inf') else "inf",
            "unique_insiders": len(unique_insiders),
            "signal": signal,
        }

    def _generate_summary(
        self,
        ticker: str,
        filings: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> str:
        """Generate summary of insider activity."""
        signal = analysis.get("signal", "neutral")
        signal_label = signal.replace("_", " ")

        return (
            f"SEC insider activity for {ticker}: {signal_label}. "
            f"{len(filings)} Form 4 filings from {analysis['unique_insiders']} insiders. "
            f"Buy/sell ratio: {analysis['buy_sell_ratio']}."
        )

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[DataSourceResult]:
        """Search SEC filings."""
        return [await self.fetch(query)]
