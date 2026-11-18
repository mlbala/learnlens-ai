"""Text model adapters."""

from app.ai.text.deepseek_adapter import DeepSeekTextAdapter
from app.ai.text.fake import FakeTextAdapter
from app.ai.text.gemini_adapter import GeminiTextAdapter
from app.ai.text.openai_adapter import OpenAITextAdapter

__all__ = [
    "FakeTextAdapter",
    "OpenAITextAdapter",
    "GeminiTextAdapter",
    "DeepSeekTextAdapter",
]
