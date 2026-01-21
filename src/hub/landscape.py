"""Landscape scoring and brief generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from src.data_sources.aggregator import AggregatedCompanyData
from src.hub.evidence import EvidenceItem
from src.hub.ontology import OntologyMapping


@dataclass
class CompanyScore:
    company_id: str
    ticker: str
    score: float
    change_1d: float
    news_count: int
    avg_sentiment: float | None


def _safe_change_1d(aggregated: AggregatedCompanyData) -> float:
    if not aggregated.price_data:
        return 0.0
    if aggregated.price_data.change_1d is not None:
        return float(aggregated.price_data.change_1d)
    prev = aggregated.price_data.previous_close or 0
    if prev <= 0:
        return 0.0
    return ((aggregated.price_data.current_price - prev) / prev) * 100


def _safe_relative_volume(aggregated: AggregatedCompanyData) -> float:
    if not aggregated.price_data:
        return 1.0
    if aggregated.price_data.relative_volume is not None:
        return float(aggregated.price_data.relative_volume)
    return 1.0


def compute_company_score(
    company_id: str,
    aggregated: AggregatedCompanyData,
    evidence: List[EvidenceItem],
) -> CompanyScore:
    change_1d = _safe_change_1d(aggregated)
    rel_vol = _safe_relative_volume(aggregated)

    recent_cutoff = datetime.utcnow() - timedelta(days=7)
    recent_news = [item for item in evidence if item.source_type == "news" and item.timestamp >= recent_cutoff]
    news_count = len(recent_news)

    sentiments = [item.sentiment for item in recent_news if item.sentiment is not None]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None

    price_component = max(min(change_1d, 10.0), -10.0) * 2.0
    volume_component = min(rel_vol, 3.0) * 5.0
    news_component = min(news_count, 10) * 2.0
    sentiment_component = (avg_sentiment or 0.0) * 10.0

    raw_score = 50.0 + price_component + volume_component + news_component + sentiment_component
    score = max(min(raw_score, 100.0), 0.0)

    return CompanyScore(
        company_id=company_id,
        ticker=aggregated.ticker,
        score=score,
        change_1d=change_1d,
        news_count=news_count,
        avg_sentiment=avg_sentiment,
    )


def compute_theme_scores(
    mapping: OntologyMapping,
    company_scores: Dict[str, CompanyScore],
) -> Dict[str, float]:
    theme_scores: Dict[str, float] = {}
    for theme_id in mapping.theme_ids:
        exposures = mapping.get_theme_companies(theme_id)
        if not exposures:
            continue
        weighted_sum = 0.0
        total_weight = 0.0
        for company_id, weight in exposures:
            score = company_scores.get(company_id)
            if not score:
                continue
            weighted_sum += score.score * weight
            total_weight += weight
        if total_weight > 0:
            theme_scores[theme_id] = weighted_sum / total_weight
    return theme_scores


def compute_vertical_scores(
    mapping: OntologyMapping,
    theme_scores: Dict[str, float],
) -> Dict[str, float]:
    vertical_scores: Dict[str, float] = {}
    for vertical_id in mapping.vertical_ids:
        related_themes = [row["theme_id"] for row in mapping.theme_vertical_aspect if row["vertical_id"] == vertical_id]
        if not related_themes:
            continue
        values = [theme_scores.get(theme_id, 0.0) for theme_id in related_themes]
        if values:
            vertical_scores[vertical_id] = sum(values) / len(values)
    return vertical_scores


def compute_aspect_scores(
    mapping: OntologyMapping,
    theme_scores: Dict[str, float],
) -> Dict[str, float]:
    aspect_scores: Dict[str, float] = {}
    for row in mapping.aspect_theme_weighting:
        aspect_id = row["aspect_id"]
        theme_id = row["theme_id"]
        weight = float(row.get("weight", 0))
        score = theme_scores.get(theme_id)
        if score is None:
            continue
        aspect_scores.setdefault(aspect_id, 0.0)
        aspect_scores[aspect_id] += score * weight
    return aspect_scores


def rank_items(scores: Dict[str, float], top_n: int) -> List[Tuple[str, float]]:
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]


def build_landscape_summary(
    top_verticals: List[Tuple[str, float]],
    top_aspects: List[Tuple[str, float]],
    top_companies: List[CompanyScore],
) -> str:
    vertical_text = ", ".join([f"{vid} ({score:.1f})" for vid, score in top_verticals])
    aspect_text = ", ".join([f"{aid} ({score:.1f})" for aid, score in top_aspects])
    company_text = ", ".join([f"{c.ticker} ({c.score:.1f})" for c in top_companies])

    return (
        f"Top verticals: {vertical_text}\n"
        f"Top aspects: {aspect_text}\n"
        f"Top companies: {company_text}"
    )

