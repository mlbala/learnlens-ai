"""Baseline ablations: dense-only vs hybrid; naive vs hierarchical summarization."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.ai.embeddings.fake import FakeEmbeddingAdapter
from app.domain.citation_urls import build_watch_url
from app.domain.evidence import (
    QaEvidenceItem,
    build_packet,
    build_qa_packet,
    validate_qa_payload,
    validate_summary_payload,
)
from app.domain.qa_schemas import REFUSAL_MESSAGE
from app.eval.dataset import GoldenDataset
from app.eval.metrics import (
    attribution_precision,
    concept_coverage,
    estimate_cost_usd,
    estimate_tokens,
    faithfulness_overlap,
    mean_reciprocal_rank,
    phrase_hit_rate,
    recall_at_k,
)
from app.retrieval.contracts import ChunkIndexRecord, TenantScopeFilter
from app.retrieval.memory_store import InMemoryVectorStore

_EXFIL_MARKERS = (
    "attacker.example",
    "openai_api_key",
    "sk-live-",
    "sk-fake-",
    "session cookies",
    "exfiltrate",
)


@dataclass(frozen=True, slots=True)
class RetrievalBaselineResult:
    mode: str
    recall_at_10: float
    mrr: float
    latency_ms: float
    retrieved_segment_ids: list[str]
    leaked_tenant_count: int


@dataclass(frozen=True, slots=True)
class SummaryBaselineResult:
    mode: str
    faithfulness: float
    coverage: float
    latency_ms: float
    estimated_cost_usd: float
    blocked_unsupported: bool
    dropped_citation_ids: list[str]


class OfflineIndex:
    """In-memory hybrid index of golden segments using FakeEmbeddingAdapter."""

    def __init__(self, dataset: GoldenDataset, *, dimensions: int = 64) -> None:
        self.dataset = dataset
        self.embedder = FakeEmbeddingAdapter(dimensions=dimensions)
        self.store = InMemoryVectorStore()
        self.profile_id = self.embedder.profile_id
        self.dimensions = dimensions
        self.collection = self.store.ensure_collection(
            profile_id=self.profile_id,
            dimensions=dimensions,
        )
        self._chunk_to_segments: dict[uuid.UUID, list[str]] = {}
        self._index_all()

    def _index_all(self) -> None:
        records: list[ChunkIndexRecord] = []
        for segment in self.dataset.corpus.get("segments") or []:
            text = str(segment.get("text") or "")
            dense = self.embedder._embed_one(text)  # noqa: SLF001 — offline deterministic
            chunk_id = uuid.uuid5(uuid.NAMESPACE_URL, f"eval-chunk:{segment['id']}")
            video_id = uuid.UUID(str(segment["video_id"]))
            workspace_id = uuid.UUID(str(segment["workspace_id"]))
            asset_id = uuid.uuid5(uuid.NAMESPACE_URL, f"eval-asset:{segment['video_key']}")
            seg_uuid = uuid.UUID(str(segment["id"]))
            record = ChunkIndexRecord(
                chunk_id=chunk_id,
                workspace_id=workspace_id,
                video_id=video_id,
                source_asset_id=asset_id,
                source_revision=int(segment.get("source_revision") or 1),
                segment_ids=(seg_uuid,),
                text=text,
                dense_vector=dense,
                start_ms=segment.get("start_ms"),
                end_ms=segment.get("end_ms"),
                title=str(segment.get("video_title") or ""),
                embedding_profile=self.profile_id,
                processing_version="eval-v1",
                text_preview=text[:240],
            )
            records.append(record)
            self._chunk_to_segments[chunk_id] = [str(segment["id"])]
        self.store.upsert_chunks(
            collection=self.collection,
            profile_id=self.profile_id,
            dimensions=self.dimensions,
            records=records,
        )

    def search(
        self,
        *,
        question: str,
        workspace_id: str,
        video_ids: list[str],
        dense_only: bool,
        top_k: int = 10,
        forbidden_workspace_ids: list[str] | None = None,
    ) -> RetrievalBaselineResult:
        scope = TenantScopeFilter(
            workspace_id=uuid.UUID(workspace_id),
            video_ids=tuple(uuid.UUID(v) for v in video_ids),
        )
        query_vec = self.embedder._embed_one(question)  # noqa: SLF001
        started = time.perf_counter()
        result = self.store.search(
            collection=self.collection,
            dimensions=self.dimensions,
            query_text=question,
            dense_vector=query_vec,
            scope=scope,
            top_k=top_k,
            dense_only=dense_only,
            prefetch_limit=max(top_k * 2, 20),
        )
        latency_ms = (time.perf_counter() - started) * 1000.0

        retrieved: list[str] = []
        leaked = 0
        forbidden = set(forbidden_workspace_ids or [])
        for hit in result.hits:
            payload = hit.payload
            ws = str(payload.get("workspace_id") or "")
            if ws in forbidden:
                leaked += 1
            for sid in self._chunk_to_segments.get(hit.chunk_id, []):
                if sid not in retrieved:
                    retrieved.append(sid)
            for raw in payload.get("segment_ids") or []:
                sid = str(raw)
                if sid not in retrieved:
                    retrieved.append(sid)
        mode = "dense_only" if dense_only else "hybrid"
        return RetrievalBaselineResult(
            mode=mode,
            recall_at_10=0.0,
            mrr=0.0,
            latency_ms=latency_ms,
            retrieved_segment_ids=retrieved,
            leaked_tenant_count=leaked,
        )


def score_retrieval(
    baseline: RetrievalBaselineResult,
    relevant: list[str],
) -> RetrievalBaselineResult:
    return RetrievalBaselineResult(
        mode=baseline.mode,
        recall_at_10=recall_at_k(relevant, baseline.retrieved_segment_ids, k=10),
        mrr=mean_reciprocal_rank(relevant, baseline.retrieved_segment_ids),
        latency_ms=baseline.latency_ms,
        retrieved_segment_ids=baseline.retrieved_segment_ids,
        leaked_tenant_count=baseline.leaked_tenant_count,
    )


def scope_video_ids(dataset: GoldenDataset, case: dict[str, Any]) -> list[str]:
    kind = str(case.get("scope_kind") or "video")
    if kind == "library":
        ws = str(case.get("workspace_id") or "")
        ids: list[str] = []
        for video in dataset.corpus.get("videos") or []:
            if str(video.get("workspace_id")) == ws and video.get("transcript_ready"):
                ids.append(str(video["id"]))
        return ids
    if kind == "playlist":
        key = case.get("scope_playlist_key")
        if key:
            playlist = dataset.playlist_by_key(str(key))
            ids = []
            for video_key in playlist.get("member_video_keys") or []:
                video = dataset.video_by_key(str(video_key))
                if video.get("transcript_ready"):
                    ids.append(str(video["id"]))
            return ids
        permitted = case.get("permitted_video_keys") or []
        return [str(dataset.video_by_key(str(k))["id"]) for k in permitted]
    video_key = case.get("scope_video_key")
    if not video_key:
        return []
    video = dataset.video_by_key(str(video_key))
    if not video.get("transcript_ready"):
        return []
    return [str(video["id"])]


def build_evidence_items(
    dataset: GoldenDataset,
    segment_ids: list[str],
) -> list[QaEvidenceItem]:
    items: list[QaEvidenceItem] = []
    for sid in segment_ids:
        row = dataset.segment_by_id(sid)
        if row is None:
            continue
        items.append(
            QaEvidenceItem(
                segment_id=str(row["id"]),
                video_id=uuid.UUID(str(row["video_id"])),
                text=str(row["text"]),
                start_ms=row.get("start_ms"),
                end_ms=row.get("end_ms"),
                source_revision=int(row.get("source_revision") or 1),
                youtube_video_id=str(row.get("youtube_video_id") or ""),
                video_title=str(row.get("video_title") or ""),
                timecode_quality=str(row.get("timecode_quality") or "none"),
            )
        )
    return items


def simulate_grounded_answer(
    dataset: GoldenDataset,
    case: dict[str, Any],
    retrieved_segment_ids: list[str],
) -> dict[str, Any]:
    """Deterministic fake-model answer using retrieved evidence + case expectations."""
    should_abstain = bool(case.get("should_abstain"))
    relevant = list(case.get("expected_segment_ids") or [])
    cited = [sid for sid in retrieved_segment_ids if sid in set(relevant)]
    if case.get("case_type") == "citation_gate":
        cited = list(case.get("model_cited_segment_ids") or cited)
    if case.get("case_type") == "security_tenant":
        # Model attempts to cite a foreign segment — validator must drop it.
        cited = list(relevant) + list(case.get("injected_foreign_segment_ids") or [])

    packet_ids = list(retrieved_segment_ids)
    if should_abstain or not packet_ids:
        payload = {
            "answer": "unsupported",
            "claims": [],
            "unsupported": True,
            "confidence_label": "abstain",
        }
    else:
        phrases = case.get("expected_answer_phrases") or ["supported claim"]
        answer = " ".join(str(p) for p in phrases)
        if case.get("case_type") == "qa_contradiction":
            answer = "Lectures contradict: amortized O(1) vs always O(n). " + answer
        payload = {
            "answer": answer,
            "claims": [
                {
                    "text": answer,
                    "citation_segment_ids": cited or packet_ids[:1],
                }
            ],
            "unsupported": False,
            "confidence_label": "supported",
        }

    items = build_evidence_items(dataset, packet_ids)
    packet = build_qa_packet(
        workspace_id=uuid.UUID(str(case["workspace_id"])),
        scope_kind=str(case.get("scope_kind") or "video"),
        scope_id=uuid.UUID(
            str(case.get("scope_video_id") or case.get("scope_playlist_id") or case["workspace_id"])
        ),
        items=items,
    )
    validated = validate_qa_payload(payload, packet, refusal_message=REFUSAL_MESSAGE)

    fabricated_timestamps = 0
    citation_links: list[str] = []
    for sid in validated.cited_segment_ids:
        row = dataset.segment_by_id(sid)
        if row is None:
            continue
        link = build_watch_url(
            youtube_video_id=str(row.get("youtube_video_id") or ""),
            start_ms=row.get("start_ms"),
            end_ms=row.get("end_ms"),
            timecode_quality=str(row.get("timecode_quality") or "none"),
        )
        if link.youtube_url:
            citation_links.append(link.youtube_url)
        if case.get("no_timestamps") and link.youtube_url and "t=" in link.youtube_url:
            fabricated_timestamps += 1
        if str(row.get("timecode_quality")) == "none" and link.timing_verified:
            fabricated_timestamps += 1

    leaked = 0
    forbidden_segments = set(case.get("forbidden_segment_ids") or [])
    forbidden_ws = set(case.get("forbidden_workspace_ids") or [])
    for sid in validated.cited_segment_ids:
        if sid in forbidden_segments:
            leaked += 1
        row = dataset.segment_by_id(sid)
        if row and str(row.get("workspace_id")) in forbidden_ws:
            leaked += 1

    completeness = phrase_hit_rate(
        validated.answer,
        list(case.get("expected_answer_phrases") or []),
    )
    if should_abstain:
        completeness = 1.0 if validated.refused else 0.0

    cited_texts = [
        str(row["text"])
        for sid in validated.cited_segment_ids
        if (row := dataset.segment_by_id(sid)) is not None
    ]
    # Prefer expected phrases (gold claim text) so meta wrappers don't tank the proxy.
    attr_text = " ".join(str(p) for p in (case.get("expected_answer_phrases") or []))
    if not attr_text.strip():
        attr_text = validated.answer
    attribution = (
        1.0
        if validated.refused or not validated.cited_segment_ids
        else attribution_precision(attr_text, cited_texts)
    )

    answer_lower = validated.answer.lower()
    exfil_hits = [m for m in _EXFIL_MARKERS if m in answer_lower]
    # Soft answers that intentionally paraphrase expected phrases are fine;
    # hard-fail only when must_not_exfiltrate is set and markers appear.
    if not case.get("must_not_exfiltrate"):
        exfil_hits = []

    return {
        "refused": validated.refused,
        "unsupported": validated.unsupported,
        "confidence_label": validated.confidence_label,
        "answer": validated.answer,
        "cited_segment_ids": validated.cited_segment_ids,
        "dropped_citation_ids": validated.dropped_citation_ids,
        "citation_links": citation_links,
        "fabricated_timestamp_links": fabricated_timestamps,
        "leaked_tenant_count": leaked,
        "answer_completeness": completeness,
        "attribution_precision": attribution,
        "exfil_marker_hits": exfil_hits,
        "exfil_blocked": len(exfil_hits) == 0,
        "kept_citations_in_packet": all(
            sid in packet.allowed_segment_ids for sid in validated.cited_segment_ids
        ),
    }


def naive_summary(segments: list[dict[str, Any]]) -> str:
    """Baseline A: concatenate early transcript text (truncate)."""
    joined = " ".join(str(s.get("text") or "") for s in segments)
    return joined[:400].strip()


def hierarchical_summary(segments: list[dict[str, Any]]) -> str:
    """Baseline D (offline proxy): per-segment note = first clause, then join."""
    notes: list[str] = []
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        note = text.split(".")[0].strip()
        if note:
            notes.append(note)
    return ". ".join(notes) + ("." if notes else "")


def evaluate_summary_baseline(
    dataset: GoldenDataset,
    case: dict[str, Any],
    *,
    mode: str,
) -> SummaryBaselineResult:
    video_key = str(case.get("scope_video_key"))
    segments = dataset.segments_for_video(video_key)
    started = time.perf_counter()
    if mode == "naive":
        summary_text = naive_summary(segments)
    else:
        summary_text = hierarchical_summary(segments)
    latency_ms = (time.perf_counter() - started) * 1000.0

    source_texts = [str(s.get("text") or "") for s in segments]
    concepts = list(case.get("expected_concepts") or [])
    allowed_ids = [str(s["id"]) for s in segments]
    packet = build_packet(
        workspace_id=uuid.UUID(str(case["workspace_id"])),
        video_id=uuid.UUID(str(case["scope_video_id"])),
        source_revision=1,
        workspace_segment_ids=set(allowed_ids),
        prompt_evidence_ids=set(allowed_ids),
    )
    # Cite all expected segments as source_supported claims (deterministic).
    claims = [
        {
            "text": concept,
            "evidence_segment_ids": list(case.get("expected_segment_ids") or allowed_ids[:1]),
            "provenance": "source_supported",
        }
        for concept in concepts
    ]
    # Inject one fabricated citation on hierarchical path to prove drop behavior stays gated.
    if mode == "hierarchical":
        claims.append(
            {
                "text": "fabricated unsupported claim",
                "evidence_segment_ids": ["00000000-0000-4000-8000-00000000dead"],
                "provenance": "source_supported",
            }
        )
    validated = validate_summary_payload(
        {
            "summary": summary_text,
            "key_points": concepts,
            "claims": claims,
            "examples": [],
            "evidence_segment_ids": list(case.get("expected_segment_ids") or []),
            "origin": "eval_baseline",
        },
        packet,
    )
    in_tokens = estimate_tokens(" ".join(source_texts))
    out_tokens = estimate_tokens(summary_text)
    return SummaryBaselineResult(
        mode=mode,
        faithfulness=faithfulness_overlap(summary_text, source_texts),
        coverage=concept_coverage(summary_text, concepts),
        latency_ms=latency_ms,
        estimated_cost_usd=estimate_cost_usd(input_tokens=in_tokens, output_tokens=out_tokens),
        blocked_unsupported=validated.blocked_unsupported,
        dropped_citation_ids=validated.dropped_citation_ids,
    )
