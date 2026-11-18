"""OpenAI embedding adapter — official embeddings.create."""

from __future__ import annotations

from typing import Any

from app.ai.allowlist import embedding_profile_id
from app.ai.contracts import ModelCapabilities
from app.ai.embeddings.validate import assert_vector
from app.ai.errors import ProviderConfigurationError
from app.ai.retry import with_bounded_retry
from app.ai.status_map import map_sdk_exception


class OpenAIEmbeddingAdapter:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is not configured.",
                provider=self.provider,
                details={"error_kind": "missing_key"},
            )
        self.model = model
        self._dimensions = dimensions
        self.max_retries = max_retries
        self.profile_id = embedding_profile_id(self.provider, model, dimensions)
        self.capabilities = ModelCapabilities(
            supports_json_schema=False,
            supports_stream=False,
            supports_vision=False,
            supports_batch=True,
            max_context_tokens=8_192,
        )
        if client is not None:
            self._client = client
        else:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async def _once() -> list[list[float]]:
            return await self._embed(texts)

        return await with_bounded_retry(
            _once, max_retries=self.max_retries, provider=self.provider
        )

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_documents([text])
        return vectors[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self._dimensions,
            )
        except TypeError:
            # Older models may reject dimensions=; retry without.
            try:
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
            except Exception as exc:  # noqa: BLE001
                raise map_sdk_exception(exc, provider=self.provider) from exc
        except Exception as exc:  # noqa: BLE001
            raise map_sdk_exception(exc, provider=self.provider) from exc

        data = sorted(getattr(response, "data", []), key=lambda row: getattr(row, "index", 0))
        return [
            assert_vector(
                list(getattr(row, "embedding", [])),
                expected_dimensions=self._dimensions,
                provider=self.provider,
            )
            for row in data
        ]

    async def health(self) -> dict[str, str]:
        return {
            "status": "configured",
            "provider": self.provider,
            "model": self.model,
            "profile_id": self.profile_id,
        }
