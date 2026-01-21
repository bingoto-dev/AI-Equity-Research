"""Theme memo generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from src.hub.evidence import EvidenceItem
from src.hub.ontology import OntologyMapping
from src.hub.landscape import CompanyScore


@dataclass
class MemoScore:
    role: str
    conviction: float
    differentiation: float
    magnitude: float
    timing: float
    reversibility: float
    risk_awareness: float
    evidence_quality: float

    @property
    def aggregate(self) -> float:
        return (
            self.conviction
            + self.differentiation
            + self.magnitude
            + self.timing
            + self.reversibility
            + self.risk_awareness
            + self.evidence_quality
        ) / 7.0


def _keyword_hits(text: str, keywords: List[str]) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def select_catalysts(evidence: List[EvidenceItem]) -> List[str]:
    catalysts = []
    keywords = ["earnings", "guidance", "launch", "contract", "policy", "regulation", "price", "upgrade"]
    for item in evidence:
        text = f"{item.title} {item.summary}"
        if _keyword_hits(text, keywords):
            catalysts.append(f"{item.title} ({item.source_type})")
        if len(catalysts) >= 5:
            break
    return catalysts


def compute_scores(evidence: List[EvidenceItem], catalysts: List[str]) -> List[MemoScore]:
    evidence_count = len(evidence)
    conviction = min(5.0, 1.0 + evidence_count / 3.0)
    differentiation = 3.0
    magnitude = 3.0
    timing = 3.0 if catalysts else 2.0
    reversibility = 3.0
    risk_awareness = 3.0 if evidence_count > 0 else 2.0
    evidence_quality = min(5.0, 1.0 + evidence_count / 4.0)

    roles = ["fundamental", "macro", "risk", "technical"]
    scores = []
    for role in roles:
        if role == "risk":
            scores.append(MemoScore(
                role=role,
                conviction=conviction - 0.3,
                differentiation=differentiation,
                magnitude=magnitude,
                timing=timing,
                reversibility=reversibility + 0.2,
                risk_awareness=min(5.0, risk_awareness + 0.5),
                evidence_quality=evidence_quality,
            ))
        elif role == "macro":
            scores.append(MemoScore(
                role=role,
                conviction=conviction,
                differentiation=differentiation + 0.2,
                magnitude=magnitude + 0.2,
                timing=timing,
                reversibility=reversibility,
                risk_awareness=risk_awareness,
                evidence_quality=evidence_quality,
            ))
        else:
            scores.append(MemoScore(
                role=role,
                conviction=conviction,
                differentiation=differentiation,
                magnitude=magnitude,
                timing=timing,
                reversibility=reversibility,
                risk_awareness=risk_awareness,
                evidence_quality=evidence_quality,
            ))
    return scores


def build_theme_memo_context(
    theme_id: str,
    mapping: OntologyMapping,
    company_scores: Dict[str, CompanyScore],
    evidence: List[EvidenceItem],
    macro_summary: Optional[str],
    date_str: str,
) -> Dict[str, object]:
    theme_name = theme_id
    verticals = mapping.get_theme_verticals(theme_id)
    aspects = mapping.get_theme_aspects(theme_id)
    theme_companies = mapping.get_theme_companies(theme_id)
    ranked_companies: List[Tuple[str, float]] = []
    for company_id, exposure in theme_companies:
        score = company_scores.get(company_id)
        if not score:
            continue
        ranked_companies.append((company_id, exposure * score.score))
    ranked_companies.sort(key=lambda x: x[1], reverse=True)

    top_companies = []
    for company_id, _ in ranked_companies[:5]:
        score = company_scores.get(company_id)
        if not score:
            continue
        top_companies.append({
            "company_id": company_id,
            "ticker": score.ticker,
            "score": score.score,
            "change_1d": score.change_1d,
        })

    catalysts = select_catalysts(evidence)

    thesis = (
        f"{theme_name} shows elevated activity based on recent news flow and "
        f"price action in the highest-exposure companies."
    )
    mechanism = (
        "Capacity build-outs, cost dynamics, and competitive positioning "
        "are the primary drivers for this theme in the current cycle."
    )

    first_order = [
        f"Direct impact on {item['ticker']} revenue or margins via AI demand or spend cycles."
        for item in top_companies
    ]
    second_order = [
        f"Spillover to verticals: {', '.join(verticals) or 'N/A'}."
    ]
    third_order = [
        f"Macro and policy effects: {macro_summary or 'Limited macro linkage detected in current data.'}"
    ]

    causal_chain = []
    for vertical in verticals or ["N/A"]:
        for aspect in aspects or ["N/A"]:
            causal_chain.append(f"{theme_id} -> {vertical} -> {aspect}")
            if len(causal_chain) >= 5:
                break
        if len(causal_chain) >= 5:
            break

    risks = [
        "Demand normalization after near-term pull-forward.",
        "Capex delays or policy headwinds reducing forward spend."
    ]

    actionability = (
        "Edge may exist where consensus underweights second-order effects "
        "from supply-chain and capex constraints."
    )

    scores = compute_scores(evidence, catalysts)
    aggregate_score = sum(score.aggregate for score in scores) / len(scores)

    return {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "date": date_str,
        "verticals": verticals,
        "aspects": aspects,
        "thesis": thesis,
        "mechanism": mechanism,
        "evidence": evidence[:10],
        "first_order": first_order,
        "second_order": second_order,
        "third_order": third_order,
        "causal_chain": causal_chain,
        "catalysts": catalysts or ["No near-term catalysts detected"],
        "risks": risks,
        "top_companies": top_companies,
        "actionability": actionability,
        "macro_summary": macro_summary or "N/A",
        "scores": scores,
        "aggregate_score": aggregate_score,
    }
