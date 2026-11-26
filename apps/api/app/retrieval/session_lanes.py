"""Lane filter, in-lane rerank, and the lesson decision. No raw scores leave this module."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.ai.contracts import ModelRequest, TextModel
from app.retrieval.thresholds import (
    EXTERNAL_KEEP_THRESHOLD,
    EXTERNAL_SOURCE_LIMIT,
    VIDEO_COVERAGE_THRESHOLD,
    VIDEO_PASSAGE_LIMIT,
)

logger = logging.getLogger(__name__)

ORIGIN_VIDEO = "video_transcript"
ORIGIN_EXTERNAL = "external_search"
ABSTAIN_HEADING = "Coverage"
ABSTAIN_BODY = "The video does not cover this question."
RERANK_PURPOSE = "session_rerank"

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "is",
        "it",
        "that",
        "this",
        "did",
        "was",
        "what",
        "how",
        "do",
    }
)
_ACADEMIC = (
    "arxiv.org",
    "doi.org",
    "semanticscholar.org",
    "acm.org",
    "nature.com",
    "pubmed",
    "openalex.org",
)
_OFFICIAL = (
    "/docs/",
    "readthedocs.io",
    "developer.mozilla",
    "docs.python.org",
    "learn.microsoft.com",
    "ai.google.dev",
)

RERANK_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["ranked"],
    "properties": {
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "score"],
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "number"},
                },
            },
        }
    },
}


@dataclass(frozen=True, slots=True)
class LanePassage:
    id: uuid.UUID
    evidence_origin: str
    evidence_provider: str
    text: str
    title: str = ""
    source_url: str = ""


@dataclass(frozen=True, slots=True)
class ScoredPassage:
    passage: LanePassage
    score: float


class SessionReranker(Protocol):
    async def rerank(
        self,
        *,
        question: str,
        passages: list[LanePassage],
    ) -> list[tuple[uuid.UUID, float]]: ...


def stable_point_id(
    *,
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    evidence_origin: str,
    content_hash: str,
) -> uuid.UUID:
    """One Qdrant point for this workspace, thread, origin, and passage hash."""
    raw = f"{workspace_id}|{thread_id}|{evidence_origin}|{content_hash}"
    return uuid.uuid5(uuid.NAMESPACE_URL, raw)


def stored_timing(start_ms: int | None, end_ms: int | None) -> tuple[int | None, int | None]:
    """Timestamps stay null unless the Neon row already has both ends."""
    if start_ms is None or end_ms is None:
        return None, None
    return start_ms, end_ms


def source_kind(url: str) -> str:
    lowered = url.lower()
    if any(host in lowered for host in _ACADEMIC):
        return "paper"
    if any(token in lowered for token in _OFFICIAL):
        return "official"
    return "other"


def decide(*, external_search: bool, best_video_score: float, external_kept: int) -> str:
    """lesson_only, blend, or abstain. A higher outside score cannot change the video gate."""
    video_ok = best_video_score >= VIDEO_COVERAGE_THRESHOLD
    if external_search and external_kept > 0:
        return "blend"
    if video_ok:
        return "lesson_only"
    return "abstain"


def evidence_block(passages: list[LanePassage]) -> str:
    """Video passages first. Each block is labeled. Scores are omitted."""
    if not passages:
        return ""
    lines = ["CURRENT EVIDENCE:"]
    for passage in passages:
        lines.append(f"BLOCK {passage.evidence_origin} id={passage.id}")
        lines.append(passage.text.strip())
        lines.append("")
    return "\n".join(lines).strip()


def kept_refs(passages: list[LanePassage]) -> list[dict[str, str]]:
    return [
        {"id": str(passage.id), "evidence_origin": passage.evidence_origin}
        for passage in passages
    ]


def lexical_score(question: str, text: str) -> float:
    query = _tokens(question)
    if not query:
        return 0.0
    return len(query & _tokens(text)) / len(query)


def lexical_rank(question: str, passages: list[LanePassage]) -> list[ScoredPassage]:
    return [ScoredPassage(passage, lexical_score(question, passage.text)) for passage in passages]


def select_kept(
    scored: list[ScoredPassage],
    *,
    threshold: float,
    limit: int,
) -> list[LanePassage]:
    ranked = sorted(scored, key=lambda row: (-row.score, str(row.passage.id)))
    return [row.passage for row in ranked if row.score >= threshold][:limit]


def best_score(scored: list[ScoredPassage]) -> float:
    if not scored:
        return 0.0
    return max(row.score for row in scored)


async def rank_lane(
    *,
    question: str,
    passages: list[LanePassage],
    origin: str,
    text_model: TextModel | None = None,
    reranker: SessionReranker | None = None,
) -> tuple[list[ScoredPassage], list[LanePassage]]:
    """Rerank inside one lane. A failed model call uses lexical overlap in that same lane."""
    if not passages:
        return [], []
    threshold = VIDEO_COVERAGE_THRESHOLD if origin == ORIGIN_VIDEO else EXTERNAL_KEEP_THRESHOLD
    limit = VIDEO_PASSAGE_LIMIT if origin == ORIGIN_VIDEO else EXTERNAL_SOURCE_LIMIT
    try:
        if reranker is not None:
            scored = _from_pairs(
                passages,
                await reranker.rerank(question=question, passages=passages),
            )
        elif text_model is None:
            raise RuntimeError("No rerank model is configured.")
        else:
            scored = await _model_rank(text_model, question, passages)
    except Exception:
        logger.info(
            "session_rerank_lexical_fallback",
            extra={"evidence_origin": origin, "passage_count": len(passages)},
        )
        scored = lexical_rank(question, passages)
    return scored, select_kept(scored, threshold=threshold, limit=limit)


async def _model_rank(
    text_model: TextModel,
    question: str,
    passages: list[LanePassage],
) -> list[ScoredPassage]:
    listing = "\n\n".join(
        f"PASSAGE {passage.id}\n{passage.text.strip()}" for passage in passages
    )
    result = await text_model.generate_structured(
        ModelRequest(
            purpose=RERANK_PURPOSE,
            instructions=(
                "Score each passage from 0 to 1 for the question. "
                "Return JSON with ranked id and score. Do not add passages."
            ),
            user_input=f"QUESTION:\n{question.strip()}\n\n{listing}",
            evidence=[],
            response_schema=RERANK_SCHEMA,
            # Room for every candidate: about 30 tokens per id and score.
            max_output_tokens=2048,
            temperature=0.0,
            timeout_seconds=30,
            prompt_version="session-rerank-v1",
        )
    )
    ranked = result.parsed.get("ranked") if isinstance(result.parsed, dict) else None
    if not isinstance(ranked, list):
        raise ValueError("Rerank response did not include ranked passages.")
    pairs: list[tuple[uuid.UUID, float]] = []
    for item in ranked:
        if not isinstance(item, dict):
            continue
        try:
            passage_id = uuid.UUID(str(item.get("id") or ""))
            score = float(item.get("score"))
        except (TypeError, ValueError):
            continue
        pairs.append((passage_id, max(0.0, min(1.0, score))))
    if not pairs:
        raise ValueError("Rerank response did not name any known passage.")
    return _from_pairs(passages, pairs)


def _from_pairs(
    passages: list[LanePassage],
    pairs: list[tuple[uuid.UUID, float]],
) -> list[ScoredPassage]:
    scores = {passage_id: score for passage_id, score in pairs}
    return [
        ScoredPassage(passage, max(0.0, min(1.0, float(scores.get(passage.id, 0.0)))))
        for passage in passages
    ]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(text.lower())
        if len(token) > 1 and token not in _STOP
    }
