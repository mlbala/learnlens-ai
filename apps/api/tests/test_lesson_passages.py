"""Lesson passages for retrieval, and reuse of points that are already indexed."""

from __future__ import annotations

import uuid

import anyio
import pytest
from app.core.settings import Settings
from app.retrieval import factory as retrieval_factory
from app.services import session_evidence
from app.services.lesson_history import (
    OVERVIEW_PREFIX,
    PASSAGE_CHARS,
    lesson_passages,
    passage_hash,
    split_transcript,
)
from app.services.session_evidence import OriginPoint, index_origin_points


def test_short_paragraphs_stay_one_passage_each() -> None:
    assert split_transcript("First idea.\n\nSecond idea.") == ["First idea.", "Second idea."]
    assert split_transcript("Line one.\nLine two.") == ["Line one.", "Line two."]


def test_a_long_paragraph_is_cut_at_sentence_ends() -> None:
    sentence = "Sovereign AI keeps data, models, and inference under the owner's control. "
    paragraph = (sentence * 40).strip()
    passages = split_transcript(paragraph)
    assert len(passages) > 1
    assert all(len(passage) <= PASSAGE_CHARS for passage in passages)
    assert all(passage.endswith(".") for passage in passages)
    assert " ".join(passages) == paragraph


def test_a_sentence_longer_than_a_passage_is_cut_between_words() -> None:
    words = " ".join(["governance"] * 300)
    passages = split_transcript(words)
    assert len(passages) > 1
    assert all(len(passage) <= PASSAGE_CHARS for passage in passages)
    assert " ".join(passages) == words


def test_overview_comes_first_and_repeats_are_dropped() -> None:
    passages = lesson_passages(
        "The talk opens with teams adopting AI.\n\nThe talk opens with teams adopting AI.",
        "Sovereign AI gives an organization control of its AI lifecycle.",
        ["Data residency matters.", "  "],
    )
    assert passages == [
        f"{OVERVIEW_PREFIX} Sovereign AI gives an organization control of its AI lifecycle. "
        "Key points: Data residency matters.",
        "The talk opens with teams adopting AI.",
    ]


def test_no_overview_without_summary_or_points() -> None:
    assert lesson_passages("Only the transcript.", "", []) == ["Only the transcript."]


class CountingEmbedder:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.1] * self.dimensions for _ in texts]


def _point(
    text: str, segment_id: uuid.UUID, *, workspace: uuid.UUID, thread: uuid.UUID
) -> OriginPoint:
    return OriginPoint(
        workspace_id=workspace,
        video_id=workspace,
        thread_id=thread,
        evidence_origin="video_transcript",
        evidence_provider="gemini_youtube",
        content_hash=passage_hash(text),
        text=text,
        source_url="",
        source_asset_id=workspace,
        segment_id=segment_id,
    )


def test_indexed_points_are_not_embedded_again(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    retrieval_factory.reset_memory_store()
    embedder = CountingEmbedder(settings.ai_embed_dimensions)
    monkeypatch.setattr(session_evidence, "build_embedding_model", lambda _settings: embedder)
    workspace, thread = uuid.uuid4(), uuid.uuid4()
    first = _point("Passage one.", uuid.uuid4(), workspace=workspace, thread=thread)
    second = _point("Passage two.", uuid.uuid4(), workspace=workspace, thread=thread)

    anyio.run(index_origin_points, settings, [first, second])
    anyio.run(index_origin_points, settings, [first, second])
    assert embedder.calls == [["Passage one.", "Passage two."]]

    # Same text saved again as a new Neon row: the point must name the new row.
    moved = _point("Passage two.", uuid.uuid4(), workspace=workspace, thread=thread)
    anyio.run(index_origin_points, settings, [first, moved])
    assert embedder.calls[-1] == ["Passage two."]
    retrieval_factory.reset_memory_store()
