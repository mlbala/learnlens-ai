"""Evidence / citation gate for summaries — fail closed on unsupported IDs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


class EvidenceValidationError(ValueError):
    """Raised when model output cites IDs outside the authorized evidence packet."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class EvidencePacket:
    workspace_id: uuid.UUID
    video_id: uuid.UUID
    source_revision: int
    allowed_segment_ids: frozenset[str]
    prompt_evidence_ids: frozenset[str]


@dataclass
class ValidatedSummary:
    summary: str
    key_points: list[str]
    claims: list[dict[str, Any]]
    examples: list[dict[str, Any]]
    evidence_segment_ids: list[str]
    origin: str
    blocked_unsupported: bool = False
    dropped_citation_ids: list[str] = field(default_factory=list)


def build_packet(
    *,
    workspace_id: uuid.UUID,
    video_id: uuid.UUID,
    source_revision: int,
    workspace_segment_ids: set[str] | frozenset[str],
    prompt_evidence_ids: set[str] | frozenset[str] | list[str],
) -> EvidencePacket:
    prompt_ids = frozenset(str(i) for i in prompt_evidence_ids if i)
    allowed = frozenset(str(i) for i in workspace_segment_ids if i) & prompt_ids
    return EvidencePacket(
        workspace_id=workspace_id,
        video_id=video_id,
        source_revision=source_revision,
        allowed_segment_ids=allowed,
        prompt_evidence_ids=prompt_ids,
    )


def validate_summary_payload(
    payload: dict[str, Any],
    packet: EvidencePacket,
    *,
    block_on_unsupported: bool = True,
) -> ValidatedSummary:
    """
    Ensure every cited segment ID is in the prompt evidence set AND workspace revision.

    Unsupported source_supported claims are dropped; if none remain and the summary
    asserted source claims, mark blocked_unsupported when block_on_unsupported.
    """
    dropped: list[str] = []

    def _filter_ids(raw: list[Any] | None) -> list[str]:
        kept: list[str] = []
        for item in raw or []:
            sid = str(item)
            if sid in packet.allowed_segment_ids:
                kept.append(sid)
            else:
                dropped.append(sid)
        return kept

    claims_in = payload.get("claims") or []
    claims_out: list[dict[str, Any]] = []
    had_source_claim = False
    for claim in claims_in:
        if not isinstance(claim, dict):
            continue
        provenance = str(claim.get("provenance") or "source_supported")
        ids = _filter_ids(claim.get("evidence_segment_ids"))
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        if provenance == "source_supported":
            had_source_claim = True
            if not ids:
                # Unsupported source claim — drop rather than promote.
                continue
        claims_out.append(
            {
                "text": text,
                "evidence_segment_ids": ids,
                "provenance": provenance,
            }
        )

    examples_out: list[dict[str, Any]] = []
    for ex in payload.get("examples") or []:
        if not isinstance(ex, dict):
            continue
        text = str(ex.get("text") or "").strip()
        if not text:
            continue
        origin = str(ex.get("origin") or "ai_generated_illustration")
        if origin == "source_supported":
            # Examples claiming source support without IDs are relabeled.
            examples_out.append(
                {"text": text, "origin": "ai_generated_illustration"}
            )
        else:
            examples_out.append({"text": text, "origin": origin})

    evidence_ids = _filter_ids(payload.get("evidence_segment_ids"))
    # Also collect from retained claims.
    for claim in claims_out:
        for sid in claim["evidence_segment_ids"]:
            if sid not in evidence_ids:
                evidence_ids.append(sid)

    blocked = False
    summary_text = str(payload.get("summary") or "").strip()
    if had_source_claim and not claims_out and block_on_unsupported:
        blocked = True
        if not summary_text:
            raise EvidenceValidationError(
                "UNSUPPORTED_SUMMARY_CLAIMS",
                "Summary claims cited segments outside the authorized evidence packet.",
            )

    key_points = [
        str(p).strip()
        for p in (payload.get("key_points") or [])
        if str(p).strip()
    ]

    if blocked and summary_text:
        # Keep a safe abstention-style surface rather than leaking unsupported claims.
        summary_text = (
            "Summary blocked: model citations were not supported by the evidence packet."
        )
        key_points = []
        evidence_ids = []

    return ValidatedSummary(
        summary=summary_text or "No supported summary content.",
        key_points=key_points,
        claims=claims_out,
        examples=examples_out,
        evidence_segment_ids=evidence_ids,
        origin=str(payload.get("origin") or "model"),
        blocked_unsupported=blocked,
        dropped_citation_ids=sorted(set(dropped)),
    )


@dataclass(frozen=True, slots=True)
class QaEvidenceItem:
    segment_id: str
    video_id: uuid.UUID
    text: str
    start_ms: int | None
    end_ms: int | None
    source_revision: int
    youtube_video_id: str
    video_title: str
    timecode_quality: str


@dataclass(frozen=True, slots=True)
class QaEvidencePacket:
    workspace_id: uuid.UUID
    scope_kind: str
    scope_id: uuid.UUID | None
    allowed_segment_ids: frozenset[str]
    items_by_id: dict[str, QaEvidenceItem]


@dataclass
class ValidatedQaAnswer:
    answer: str
    claims: list[dict[str, Any]]
    analogies: list[dict[str, Any]]
    unsupported: bool
    confidence_label: str
    cited_segment_ids: list[str]
    dropped_citation_ids: list[str] = field(default_factory=list)
    refused: bool = False


def build_qa_packet(
    *,
    workspace_id: uuid.UUID,
    scope_kind: str,
    scope_id: uuid.UUID | None,
    items: list[QaEvidenceItem],
) -> QaEvidencePacket:
    by_id = {item.segment_id: item for item in items if item.segment_id}
    return QaEvidencePacket(
        workspace_id=workspace_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        allowed_segment_ids=frozenset(by_id.keys()),
        items_by_id=by_id,
    )


def validate_qa_payload(
    payload: dict[str, Any],
    packet: QaEvidencePacket,
    *,
    refusal_message: str,
) -> ValidatedQaAnswer:
    """
    Fail closed: every citation_segment_id must be in the retrieved evidence packet.

    Unsupported claims are dropped. If no supported claims remain for a substantive
    answer (or the model marks unsupported / packet empty), return an abstention.
    """
    dropped: list[str] = []

    def _filter_ids(raw: list[Any] | None) -> list[str]:
        kept: list[str] = []
        for item in raw or []:
            sid = str(item)
            if sid in packet.allowed_segment_ids:
                if sid not in kept:
                    kept.append(sid)
            else:
                dropped.append(sid)
        return kept

    model_unsupported = bool(payload.get("unsupported"))
    empty_packet = not packet.allowed_segment_ids

    claims_out: list[dict[str, Any]] = []
    for claim in payload.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        ids = _filter_ids(claim.get("citation_segment_ids"))
        if not ids:
            continue
        claims_out.append({"text": text, "citation_segment_ids": ids})

    analogies_out: list[dict[str, Any]] = []
    for analogy in payload.get("analogies") or []:
        if not isinstance(analogy, dict):
            continue
        text = str(analogy.get("text") or "").strip()
        if not text:
            continue
        analogies_out.append(
            {
                "text": text,
                "origin": "ai_generated_illustration",
            }
        )

    cited: list[str] = []
    for claim in claims_out:
        for sid in claim["citation_segment_ids"]:
            if sid not in cited:
                cited.append(sid)

    answer_text = str(payload.get("answer") or "").strip()
    label = str(payload.get("confidence_label") or "supported").strip() or "supported"

    refuse = empty_packet or model_unsupported or not claims_out
    if refuse:
        return ValidatedQaAnswer(
            answer=refusal_message,
            claims=[],
            analogies=[],
            unsupported=True,
            confidence_label="abstain",
            cited_segment_ids=[],
            dropped_citation_ids=sorted(set(dropped)),
            refused=True,
        )

    if label not in {"supported", "partial", "unsupported", "abstain"}:
        label = "supported" if claims_out else "abstain"

    return ValidatedQaAnswer(
        answer=answer_text or refusal_message,
        claims=claims_out,
        analogies=analogies_out,
        unsupported=False,
        confidence_label=label,
        cited_segment_ids=cited,
        dropped_citation_ids=sorted(set(dropped)),
        refused=False,
    )
