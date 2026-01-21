"""Daily hub runner for landscape and memos."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader

from config.settings import DataSourceSettings
from src.data_sources.aggregator import DataAggregator
from src.data_sources.base import DataSourceType
from src.data_sources.registry import create_enhanced_registry
from src.hub.evidence import build_company_evidence
from src.hub.landscape import (
    CompanyScore,
    build_landscape_summary,
    compute_aspect_scores,
    compute_company_score,
    compute_theme_scores,
    compute_vertical_scores,
    rank_items,
)
from src.hub.memo import build_theme_memo_context
from src.hub.ontology import OntologyMapping

logger = logging.getLogger(__name__)


async def _load_macro_summary(registry) -> str | None:
    source = registry.get(DataSourceType.ECONOMIC)
    if not source:
        return None
    result = await source.fetch("AI", indicator_set="tech_relevant")
    if result.error:
        return None
    return result.data.get("summary") or result.data.get("context_for_equity")


async def run_daily_landscape(
    mappings_path: Path,
    output_dir: Path,
    templates_dir: Path,
    top_themes: int = 5,
    top_companies: int = 10,
    include_memos: bool = True,
) -> Dict[str, str]:
    """Run daily landscape pipeline.

    Returns:
        Dict with output paths
    """
    data_settings = DataSourceSettings()
    registry = create_enhanced_registry(
        news_api_key=(
            data_settings.news_api_key.get_secret_value() if data_settings.news_api_key else None
        ),
        alpha_vantage_key=(
            data_settings.alpha_vantage_key.get_secret_value() if data_settings.alpha_vantage_key else None
        ),
        sec_user_agent=data_settings.sec_user_agent,
        fred_api_key=(
            data_settings.fred_api_key.get_secret_value() if data_settings.fred_api_key else None
        ),
        github_token=(
            data_settings.github_token.get_secret_value() if data_settings.github_token else None
        ),
    )

    await registry.initialize_all()
    aggregator = DataAggregator(registry)

    mapping = OntologyMapping.load(mappings_path)

    company_ids = mapping.company_ids
    tickers = [mapping.company_id_to_ticker(cid) for cid in company_ids]

    logger.info("Fetching company data for %s tickers", len(tickers))
    aggregated_data = await aggregator.get_batch_data(tickers)

    evidence_map = {}
    company_scores: Dict[str, CompanyScore] = {}
    for company_id in company_ids:
        ticker = mapping.company_id_to_ticker(company_id)
        data = aggregated_data.get(ticker)
        if not data:
            continue
        evidence_items = build_company_evidence(company_id, data)
        evidence_map[company_id] = evidence_items
        company_scores[company_id] = compute_company_score(company_id, data, evidence_items)

    theme_scores = compute_theme_scores(mapping, company_scores)
    vertical_scores = compute_vertical_scores(mapping, theme_scores)
    aspect_scores = compute_aspect_scores(mapping, theme_scores)

    top_verticals = rank_items(vertical_scores, 5)
    top_aspects = rank_items(aspect_scores, 5)
    top_company_scores = sorted(company_scores.values(), key=lambda x: x.score, reverse=True)[:top_companies]

    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)

    summary_text = build_landscape_summary(top_verticals, top_aspects, top_company_scores)

    landscape_template = env.get_template("landscape_report.md.j2")
    landscape_content = landscape_template.render(
        report_date=date_str,
        summary=summary_text,
        top_verticals=top_verticals,
        top_aspects=top_aspects,
        top_companies=top_company_scores,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    landscape_path = output_dir / f"landscape_{date_str}.md"
    with open(landscape_path, "w", encoding="utf-8") as handle:
        handle.write(landscape_content)

    landscape_json = {
        "date": date_str,
        "summary": summary_text,
        "top_verticals": [{"id": vid, "score": score} for vid, score in top_verticals],
        "top_aspects": [{"id": aid, "score": score} for aid, score in top_aspects],
        "top_companies": [
            {
                "company_id": item.company_id,
                "ticker": item.ticker,
                "score": item.score,
                "change_1d": item.change_1d,
                "news_count": item.news_count,
            }
            for item in top_company_scores
        ],
    }
    landscape_json_path = output_dir / f"landscape_{date_str}.json"
    with open(landscape_json_path, "w", encoding="utf-8") as handle:
        json.dump(landscape_json, handle, indent=2)

    memo_paths: List[str] = []
    macro_summary = await _load_macro_summary(registry)

    memo_index: List[Dict[str, object]] = []
    if include_memos:
        memo_template = env.get_template("theme_memo.md.j2")
        memo_dir = output_dir / "memos"
        memo_dir.mkdir(parents=True, exist_ok=True)
        top_theme_ids = [theme for theme, _ in rank_items(theme_scores, top_themes)]

        for theme_id in top_theme_ids:
            theme_evidence: List = []
            for company_id, _ in mapping.get_theme_companies(theme_id):
                theme_evidence.extend(evidence_map.get(company_id, []))
            theme_evidence.sort(key=lambda x: x.timestamp, reverse=True)

            memo_context = build_theme_memo_context(
                theme_id=theme_id,
                mapping=mapping,
                company_scores=company_scores,
                evidence=theme_evidence,
                macro_summary=macro_summary,
                date_str=date_str,
            )

            memo_content = memo_template.render(**memo_context)
            memo_path = memo_dir / f"{theme_id}_{date_str}.md"
            with open(memo_path, "w", encoding="utf-8") as handle:
                handle.write(memo_content)
            memo_paths.append(str(memo_path))

            memo_index.append({
                "theme_id": theme_id,
                "aggregate_score": memo_context["aggregate_score"],
                "summary": memo_context["thesis"],
                "path": str(memo_path),
                "top_companies": memo_context["top_companies"],
            })

    memos_json_path = output_dir / f"memos_{date_str}.json"
    with open(memos_json_path, "w", encoding="utf-8") as handle:
        json.dump({"memos": memo_index}, handle, indent=2)

    await registry.close_all()

    return {
        "landscape": str(landscape_path),
        "memos": ", ".join(memo_paths),
    }


async def run_daily_landscape_cli(
    mappings_path: Path,
    output_dir: Path,
    templates_dir: Path,
    top_themes: int,
    top_companies: int,
    include_memos: bool,
) -> int:
    try:
        outputs = await run_daily_landscape(
            mappings_path=mappings_path,
            output_dir=output_dir,
            templates_dir=templates_dir,
            top_themes=top_themes,
            top_companies=top_companies,
            include_memos=include_memos,
        )
        logger.info("Landscape report: %s", outputs["landscape"])
        if include_memos:
            logger.info("Memos: %s", outputs["memos"])
        return 0
    except Exception as exc:
        logger.exception("Hub run failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(
        asyncio.run(
            run_daily_landscape_cli(
                mappings_path=Path("docs/spec/ONTOLOGY_MAPPINGS.json"),
                output_dir=Path("data/reports"),
                templates_dir=Path("src/reports/templates"),
                top_themes=5,
                top_companies=10,
                include_memos=True,
            )
        )
    )
