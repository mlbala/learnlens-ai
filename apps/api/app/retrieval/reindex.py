"""Safe reindex contract — never mix dimensions; preserve old collection until validated."""

from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.errors import EmbeddingProfileMismatch
from app.retrieval.profile import EmbeddingProfile, collection_name_for


@dataclass(frozen=True, slots=True)
class ReindexPlan:
    active_profile: EmbeddingProfile
    target_profile: EmbeddingProfile
    active_collection: str
    target_collection: str
    requires_reindex: bool
    reason: str


def plan_embedding_profile_change(
    *,
    active: EmbeddingProfile,
    target: EmbeddingProfile,
) -> ReindexPlan:
    """
    Chat-only model switches do not call this.

    Embedding profile / dimension changes always target a new collection name.
    """
    active_coll = collection_name_for(active.profile_id)
    target_coll = collection_name_for(target.profile_id)
    if active.profile_id == target.profile_id and active.dimensions == target.dimensions:
        return ReindexPlan(
            active_profile=active,
            target_profile=target,
            active_collection=active_coll,
            target_collection=target_coll,
            requires_reindex=False,
            reason="profiles_identical",
        )
    if active.dimensions != target.dimensions and active_coll == target_coll:
        # Defensive: collection naming must include dimensions; never share a name.
        raise EmbeddingProfileMismatch(
            "Cannot place incompatible dimensions in the same collection name.",
            expected_profile=target.profile_id,
            actual_profile=active.profile_id,
            expected_dimensions=target.dimensions,
            actual_dimensions=active.dimensions,
        )
    return ReindexPlan(
        active_profile=active,
        target_profile=target,
        active_collection=active_coll,
        target_collection=target_coll,
        requires_reindex=True,
        reason="embedding_profile_changed",
    )
