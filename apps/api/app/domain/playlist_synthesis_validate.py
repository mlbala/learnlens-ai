"""Fail-closed validation for playlist synthesis payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidatedPlaylistSynthesis:
    overview: str
    topic_modules: list[dict[str, Any]]
    learning_map: list[dict[str, Any]]
    cross_video_concepts: list[dict[str, Any]]
    redundant_topics: list[dict[str, Any]]
    key_takeaways: list[dict[str, Any]]
    origin: str
    dropped_video_ids: list[str] = field(default_factory=list)
    dropped_segment_ids: list[str] = field(default_factory=list)


def validate_playlist_synthesis_payload(
    payload: dict[str, Any],
    *,
    included_video_ids: set[str] | frozenset[str],
    allowed_segment_ids: set[str] | frozenset[str],
) -> ValidatedPlaylistSynthesis:
    """Keep only claims/modules that cite included videos and allowed segments."""
    included = frozenset(str(v) for v in included_video_ids)
    allowed = frozenset(str(s) for s in allowed_segment_ids)
    dropped_vids: list[str] = []
    dropped_segs: list[str] = []

    def filter_vids(raw: list[Any] | None) -> list[str]:
        kept: list[str] = []
        for item in raw or []:
            vid = str(item)
            if vid in included:
                if vid not in kept:
                    kept.append(vid)
            else:
                dropped_vids.append(vid)
        return kept

    def filter_segs(raw: list[Any] | None) -> list[str]:
        kept: list[str] = []
        for item in raw or []:
            sid = str(item)
            if sid in allowed:
                if sid not in kept:
                    kept.append(sid)
            else:
                dropped_segs.append(sid)
        return kept

    modules_out: list[dict[str, Any]] = []
    for mod in payload.get("topic_modules") or []:
        if not isinstance(mod, dict):
            continue
        title = str(mod.get("title") or "").strip()
        summary = str(mod.get("summary") or "").strip()
        vids = filter_vids(mod.get("video_ids"))
        segs = filter_segs(mod.get("evidence_segment_ids"))
        if not title or not summary or not vids:
            continue
        modules_out.append(
            {
                "title": title,
                "summary": summary,
                "video_ids": vids,
                "evidence_segment_ids": segs,
            }
        )

    map_out: list[dict[str, Any]] = []
    for node in payload.get("learning_map") or []:
        if not isinstance(node, dict):
            continue
        label = str(node.get("label") or "").strip()
        vids = filter_vids(node.get("video_ids"))
        if not label or not vids:
            continue
        try:
            order = int(node.get("order") or 0)
        except (TypeError, ValueError):
            order = 0
        map_out.append({"label": label, "video_ids": vids, "order": max(0, order)})
    map_out.sort(key=lambda n: n["order"])

    concepts_out: list[dict[str, Any]] = []
    for concept in payload.get("cross_video_concepts") or []:
        if not isinstance(concept, dict):
            continue
        name = str(concept.get("name") or "").strip()
        description = str(concept.get("description") or "").strip()
        vids = filter_vids(concept.get("video_ids"))
        segs = filter_segs(concept.get("evidence_segment_ids"))
        if not name or not description or not vids:
            continue
        concepts_out.append(
            {
                "name": name,
                "description": description,
                "video_ids": vids,
                "evidence_segment_ids": segs,
            }
        )

    redundant_out: list[dict[str, Any]] = []
    for group in payload.get("redundant_topics") or []:
        if not isinstance(group, dict):
            continue
        topic = str(group.get("topic") or "").strip()
        vids = filter_vids(group.get("video_ids"))
        if not topic or len(vids) < 2:
            continue
        redundant_out.append(
            {
                "topic": topic,
                "video_ids": vids,
                "note": str(group.get("note") or "").strip()[:1000],
            }
        )

    takeaways_out: list[dict[str, Any]] = []
    for takeaway in payload.get("key_takeaways") or []:
        if not isinstance(takeaway, dict):
            continue
        text = str(takeaway.get("text") or "").strip()
        if not text:
            continue
        provenance = str(takeaway.get("provenance") or "source_supported")
        vids = filter_vids(takeaway.get("source_video_ids"))
        segs = filter_segs(takeaway.get("evidence_segment_ids"))
        if provenance == "source_supported" and (not vids or not segs):
            continue
        if not vids:
            continue
        takeaways_out.append(
            {
                "text": text,
                "source_video_ids": vids,
                "evidence_segment_ids": segs,
                "provenance": provenance,
            }
        )

    overview = str(payload.get("overview") or "").strip()
    if not overview:
        overview = (
            f"Course notes cover {len(included)} included lesson(s) with permitted transcripts."
        )

    return ValidatedPlaylistSynthesis(
        overview=overview,
        topic_modules=modules_out,
        learning_map=map_out,
        cross_video_concepts=concepts_out,
        redundant_topics=redundant_out,
        key_takeaways=takeaways_out,
        origin=str(payload.get("origin") or "model"),
        dropped_video_ids=sorted(set(dropped_vids)),
        dropped_segment_ids=sorted(set(dropped_segs)),
    )
