"""Embedding profile manifest — one Qdrant collection per model/dim/version."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.allowlist import embedding_profile_id
from app.ai.embeddings.validate import assert_vector
from app.ai.errors import EmbeddingDimensionMismatch
from app.core.settings import Settings
from app.retrieval.errors import EmbeddingProfileMismatch

# Known probe used only for offline dimension verification (not real YouTube content).
DIMENSION_PROBE_TEXT = "learnlens-embedding-dimension-probe-v1"

_SAFE_SLUG = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    """Deployment-level embedding profile stored on manifests and point payloads."""

    profile_id: str
    provider: str
    model: str
    dimensions: int
    version: str = "v1"

    @property
    def collection_name(self) -> str:
        return collection_name_for(self.profile_id)


def collection_name_for(profile_id: str) -> str:
    """`learnlens_chunks_<embedding_profile_slug>_v1` — never per-user collections."""
    slug = _SAFE_SLUG.sub("-", profile_id.strip().lower()).strip("-")
    if not slug:
        raise ValueError("embedding profile_id must be non-empty")
    # Avoid double-suffix when profile_id already ends with -v1.
    if slug.endswith("-v1"):
        return f"learnlens_chunks_{slug}"
    return f"learnlens_chunks_{slug}_v1"


def active_embedding_profile(settings: Settings) -> EmbeddingProfile:
    provider = settings.ai_embed_provider.strip().lower()
    model = settings.ai_embed_model.strip()
    dimensions = int(settings.ai_embed_dimensions)
    if dimensions <= 0:
        raise EmbeddingProfileMismatch(
            "AI_EMBED_DIMENSIONS must be a positive integer.",
            expected_profile="unknown",
            expected_dimensions=dimensions,
        )
    profile_id = embedding_profile_id(provider, model, dimensions)
    return EmbeddingProfile(
        profile_id=profile_id,
        provider=provider,
        model=model,
        dimensions=dimensions,
        version="v1",
    )


def verify_vector_dimensions(
    vector: list[float],
    *,
    profile: EmbeddingProfile,
) -> list[float]:
    """Reject wrong-length / non-finite vectors before any upsert."""
    try:
        return assert_vector(
            vector,
            expected_dimensions=profile.dimensions,
            provider=profile.provider,
        )
    except EmbeddingDimensionMismatch as exc:
        raise EmbeddingProfileMismatch(
            (
                f"Vector dimension {exc.actual} does not match profile "
                f"{profile.profile_id} ({profile.dimensions}). "
                "Create a new collection and reindex; never mix dimensions."
            ),
            expected_profile=profile.profile_id,
            expected_dimensions=profile.dimensions,
            actual_dimensions=exc.actual,
        ) from exc


async def verify_embedding_adapter_dimensions(
    embedder: object,
    *,
    profile: EmbeddingProfile,
) -> list[float]:
    """
    Embed a single known probe text and assert dimensions.

    Used offline with FakeEmbeddingAdapter; never calls paid APIs from tests.
    """
    embed_query = getattr(embedder, "embed_query", None)
    if embed_query is None:
        raise EmbeddingProfileMismatch(
            "Embedding adapter does not expose embed_query.",
            expected_profile=profile.profile_id,
            expected_dimensions=profile.dimensions,
        )
    vector = await embed_query(DIMENSION_PROBE_TEXT)
    if not isinstance(vector, list):
        raise EmbeddingProfileMismatch(
            "Embedding adapter returned a non-list vector.",
            expected_profile=profile.profile_id,
            expected_dimensions=profile.dimensions,
        )
    return verify_vector_dimensions(vector, profile=profile)


def assert_compatible_collection_size(
    *,
    profile: EmbeddingProfile,
    collection_size: int | None,
) -> None:
    """Fail closed when an existing collection has a different dense size."""
    if collection_size is None:
        return
    if collection_size != profile.dimensions:
        raise EmbeddingProfileMismatch(
            (
                f"Collection dense size {collection_size} != profile "
                f"{profile.profile_id} ({profile.dimensions}). Reindex required."
            ),
            expected_profile=profile.profile_id,
            expected_dimensions=profile.dimensions,
            actual_dimensions=collection_size,
        )
