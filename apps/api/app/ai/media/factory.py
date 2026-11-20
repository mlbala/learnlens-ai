"""Media provider factory — fake by default; no paid STT/vision calls."""

from __future__ import annotations

from app.ai.media.contracts import SpeechToTextModel, VisionExtractModel
from app.ai.media.fake import FakeSpeechToTextAdapter, FakeVisionExtractAdapter
from app.core.settings import Settings


def get_speech_to_text(settings: Settings) -> SpeechToTextModel:
    provider = settings.ai_media_provider.strip().lower()
    if provider in {"fake", "fixture", ""}:
        return FakeSpeechToTextAdapter(model=settings.ai_media_stt_model)
    msg = (
        f"Media STT provider '{provider}' is not enabled offline. "
        "Use AI_MEDIA_PROVIDER=fake or request an explicit paid adapter."
    )
    raise RuntimeError(msg)


def get_vision_extract(settings: Settings) -> VisionExtractModel:
    provider = settings.ai_media_provider.strip().lower()
    if provider in {"fake", "fixture", ""}:
        return FakeVisionExtractAdapter(model=settings.ai_media_vision_model)
    msg = (
        f"Media vision provider '{provider}' is not enabled offline. "
        "Use AI_MEDIA_PROVIDER=fake or request an explicit paid adapter."
    )
    raise RuntimeError(msg)
