"""Evidence pack helpers for memos and landscape."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from src.data_sources.base import DataSourceType, NewsArticle, SECFiling
from src.data_sources.aggregator import AggregatedCompanyData


@dataclass
class EvidenceItem:
    entity_id: str
    source_type: str
    title: str
    summary: str
    url: Optional[str]
    timestamp: datetime
    sentiment: Optional[float] = None
    relevance: Optional[float] = None


def _news_to_evidence(company_id: str, article: NewsArticle) -> EvidenceItem:
    summary = article.description or article.summary or article.content or ""
    return EvidenceItem(
        entity_id=company_id,
        source_type="news",
        title=article.title,
        summary=summary,
        url=article.url,
        timestamp=article.published_at or datetime.utcnow(),
        sentiment=article.sentiment,
        relevance=article.relevance,
    )


def _filing_to_evidence(company_id: str, filing: SECFiling) -> EvidenceItem:
    summary = filing.summary or filing.description or ""
    title = f"{filing.form_type} filing"
    return EvidenceItem(
        entity_id=company_id,
        source_type="sec_filing",
        title=title,
        summary=summary,
        url=filing.file_url,
        timestamp=filing.filing_date,
    )


def _earnings_to_evidence(company_id: str, data: dict) -> Optional[EvidenceItem]:
    next_earnings = data.get("next_earnings")
    if not next_earnings:
        return None
    date = next_earnings.get("date") or next_earnings.get("date_range_start")
    title = "Upcoming earnings"
    summary = data.get("summary") or "Upcoming earnings date scheduled"
    return EvidenceItem(
        entity_id=company_id,
        source_type="earnings",
        title=title,
        summary=summary,
        url=None,
        timestamp=datetime.utcnow(),
    )


def build_company_evidence(company_id: str, aggregated: AggregatedCompanyData) -> List[EvidenceItem]:
    evidence: List[EvidenceItem] = []

    for article in aggregated.news:
        evidence.append(_news_to_evidence(company_id, article))

    for filing in aggregated.filings:
        evidence.append(_filing_to_evidence(company_id, filing))

    # Check raw results for earnings data
    raw_results = aggregated.raw_results
    for result in raw_results.values():
        if result.source == DataSourceType.FUNDAMENTAL:
            item = _earnings_to_evidence(company_id, result.data)
            if item:
                evidence.append(item)

    evidence.sort(key=lambda x: x.timestamp, reverse=True)
    return evidence

