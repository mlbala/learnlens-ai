"""One audit line per answer. Counts and ids only — no lesson text."""

from __future__ import annotations

import json
import uuid


def answer_usage_line(
    *,
    workspace_id: uuid.UUID | str,
    video_id: uuid.UUID | str,
    thread_id: uuid.UUID | str,
    decision: str,
    review_status: str,
    external_search_enabled: bool,
    review_reasons: tuple[str, ...] | list[str] = (),
    kept_video_passages: int,
    kept_outside_passages: int,
    dropped_off_subject: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    transcript: str = "",
    snippet: str = "",
    source_title: str = "",
    source_url: str = "",
) -> str:
    """JSON line of usage counts. Transcript, snippet, title, and URL are ignored."""
    # Accepted so a caller can hand over the lesson text. They are not copied.
    del transcript, snippet, source_title, source_url
    record: dict[str, object] = {
        "event": "answer_usage",
        "workspace_id": str(workspace_id),
        "video_id": str(video_id),
        "thread_id": str(thread_id),
        "decision": decision,
        "review_status": review_status,
        # Reviewer reason codes only (e.g. origin_mix). Never the draft or passages.
        "review_reasons": [str(code) for code in review_reasons],
        "external_search_enabled": bool(external_search_enabled),
        "kept_video_passages": int(kept_video_passages),
        "kept_outside_passages": int(kept_outside_passages),
        "dropped_off_subject": int(dropped_off_subject),
    }
    if input_tokens is not None:
        record["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        record["output_tokens"] = int(output_tokens)
    return json.dumps(record, sort_keys=True, separators=(",", ":"))
