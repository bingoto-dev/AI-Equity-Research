"""LLM-based analyst swarm scoring for memos."""

from __future__ import annotations

import asyncio
from typing import List, Optional

from pydantic import BaseModel, Field

from config.settings import Settings
from src.hub.memo import MemoScore, compute_scores
from src.llm.client import LLMClient


class Scorecard(BaseModel):
    conviction: float = Field(..., ge=1, le=5)
    differentiation: float = Field(..., ge=1, le=5)
    magnitude: float = Field(..., ge=1, le=5)
    timing: float = Field(..., ge=1, le=5)
    reversibility: float = Field(..., ge=1, le=5)
    risk_awareness: float = Field(..., ge=1, le=5)
    evidence_quality: float = Field(..., ge=1, le=5)
    rationale: str


ROLE_PROMPTS = {
    "fundamental": "You are a fundamental analyst focused on business quality and financial drivers.",
    "macro": "You are a macro strategist focused on transmission channels and regime sensitivity.",
    "risk": "You are a risk analyst focused on disconfirming evidence and downside risk.",
    "technical": "You are a technical analyst focused on price action, flows, and timing.",
}


def _build_prompt(role: str, memo_text: str) -> str:
    return (
        f"{ROLE_PROMPTS.get(role, '')}\n\n"
        "Score the memo on a 1-5 scale for each rubric item. Provide concise rationale.\n\n"
        "Rubric:\n"
        "- conviction\n- differentiation\n- magnitude\n- timing\n- reversibility\n- risk_awareness\n- evidence_quality\n\n"
        "Memo:\n"
        f"{memo_text}"
    )


async def _score_with_llm(client: LLMClient, role: str, memo_text: str) -> MemoScore:
    system_prompt = _build_prompt(role, memo_text)
    scorecard, _ = await client.complete_structured(
        system_prompt=system_prompt,
        user_message="Return only the JSON scorecard.",
        output_model=Scorecard,
        temperature=0.2,
        max_tokens=800,
    )

    return MemoScore(
        role=role,
        conviction=scorecard.conviction,
        differentiation=scorecard.differentiation,
        magnitude=scorecard.magnitude,
        timing=scorecard.timing,
        reversibility=scorecard.reversibility,
        risk_awareness=scorecard.risk_awareness,
        evidence_quality=scorecard.evidence_quality,
    )


async def score_memo_swarm(
    settings: Settings,
    memo_text: str,
    fallback_evidence_count: int,
    catalysts_count: int,
) -> List[MemoScore]:
    """Score memo using LLM swarm. Fallback to heuristic if no API key."""

    if not settings.hub.use_llm_scoring:
        return compute_scores([], ["catalyst"] * catalysts_count)

    if not settings.anthropic.api_key:
        return compute_scores([None] * fallback_evidence_count, ["catalyst"] * catalysts_count)

    client = LLMClient(settings.anthropic)
    roles = ["fundamental", "macro", "risk", "technical"]

    tasks = [_score_with_llm(client, role, memo_text) for role in roles]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scores: List[MemoScore] = []
    for role, result in zip(roles, results):
        if isinstance(result, Exception):
            # fallback per-role
            scores.append(MemoScore(
                role=role,
                conviction=3.0,
                differentiation=3.0,
                magnitude=3.0,
                timing=3.0,
                reversibility=3.0,
                risk_awareness=3.0,
                evidence_quality=3.0,
            ))
        else:
            scores.append(result)

    return scores
