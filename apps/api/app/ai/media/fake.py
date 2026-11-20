"""Fake STT / vision adapters — deterministic fixture outputs, no network."""

from __future__ import annotations

from app.ai.media.contracts import (
    FIXTURE_FRAMES,
    FIXTURE_SPEECH_CUES,
    MediaCue,
    MediaFrameDesc,
    SpeechToTextResult,
    VisionExtractResult,
)

# Alignment below this never becomes exact evidence timestamps.
_ALIGNMENT_FLOOR = 0.7


class FakeSpeechToTextAdapter:
    """Offline speech-to-text for authorized fixture media only."""

    def __init__(self, *, model: str = "fake-stt-v1") -> None:
        self._model = model

    @property
    def provider(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return self._model

    async def transcribe(
        self,
        *,
        media_bytes: bytes,
        media_kind: str,
        content_hash: str,
        max_duration_ms: int,
    ) -> SpeechToTextResult:
        del media_kind, content_hash, max_duration_ms
        # Tiny CPU/cost estimate proportional to payload size (capped).
        size_kb = max(1, len(media_bytes) // 1024)
        cues: list[MediaCue] = []
        for raw in FIXTURE_SPEECH_CUES:
            conf = float(raw["alignment_confidence"])
            start = raw["start_ms"]
            end = raw["end_ms"]
            if conf < _ALIGNMENT_FLOOR:
                start = None
                end = None
            cues.append(
                MediaCue(
                    ordinal=int(raw["ordinal"]),
                    text=str(raw["text"]),
                    start_ms=int(start) if start is not None else None,
                    end_ms=int(end) if end is not None else None,
                    alignment_confidence=conf,
                    provenance=str(raw["provenance"]),
                )
            )
        return SpeechToTextResult(
            cues=tuple(cues),
            provider=self.provider,
            model=self.model,
            estimated_cpu_units=min(10.0, 0.1 * size_kb),
            estimated_cost_usd=0.0,
        )


class FakeVisionExtractAdapter:
    """Offline vision frame/diagram extractor for authorized fixture media."""

    def __init__(self, *, model: str = "fake-vision-v1") -> None:
        self._model = model

    @property
    def provider(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return self._model

    async def extract_frames(
        self,
        *,
        media_bytes: bytes,
        media_kind: str,
        content_hash: str,
        max_frames: int,
    ) -> VisionExtractResult:
        del media_bytes, content_hash
        if media_kind == "audio":
            return VisionExtractResult(
                frames=(),
                provider=self.provider,
                model=self.model,
                estimated_cpu_units=0.0,
                estimated_cost_usd=0.0,
            )
        frames: list[MediaFrameDesc] = []
        for raw in FIXTURE_FRAMES[: max(0, max_frames)]:
            conf = float(raw["alignment_confidence"])
            ts = raw["timestamp_ms"]
            if conf < _ALIGNMENT_FLOOR:
                ts = None
            # Marker payload only — not real image bytes from YouTube.
            marker = f"fixture-frame-{raw['ordinal']}".encode()
            frames.append(
                MediaFrameDesc(
                    ordinal=int(raw["ordinal"]),
                    timestamp_ms=int(ts) if ts is not None else None,
                    description=str(raw["description"]),
                    frame_kind=str(raw["frame_kind"]),
                    alignment_confidence=conf,
                    provenance=str(raw["provenance"]),
                    frame_bytes=marker,
                )
            )
        return VisionExtractResult(
            frames=tuple(frames),
            provider=self.provider,
            model=self.model,
            estimated_cpu_units=min(20.0, 1.0 * len(frames)),
            estimated_cost_usd=0.0,
        )
