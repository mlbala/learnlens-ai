"""Authorized media STT/vision adapters (opt-in phase 17)."""

from app.ai.media.contracts import (
    MediaCue,
    MediaFrameDesc,
    SpeechToTextModel,
    SpeechToTextResult,
    VisionExtractModel,
    VisionExtractResult,
)
from app.ai.media.factory import get_speech_to_text, get_vision_extract

__all__ = [
    "MediaCue",
    "MediaFrameDesc",
    "SpeechToTextModel",
    "SpeechToTextResult",
    "VisionExtractModel",
    "VisionExtractResult",
    "get_speech_to_text",
    "get_vision_extract",
]
