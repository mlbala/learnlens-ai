"""Pydantic v2 request/response schemas for auth and me."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    status: str
    email_verified_at: datetime | None = None


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class MeResponse(BaseModel):
    user: UserOut
    workspace: WorkspaceOut


class AuthOkResponse(BaseModel):
    user: UserOut
    workspace: WorkspaceOut


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    youtube_video_id: str
    title: str
    status: str
    channel_title: str | None = None
    duration_seconds: int | None = None
    source_url: str | None = None
    metadata_json: dict[str, Any] | None = None
    transcript_access: bool = False
    coverage: str | None = None


class ImportNoticeOut(BaseModel):
    code: str
    message: str


class YoutubeImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    youtube_url: str = Field(min_length=8, max_length=2048)


class VideoImportResponse(BaseModel):
    video: VideoOut
    created: bool
    notices: list[ImportNoticeOut]
    companion_playlist_id: str | None = None
    # Explicit product constraint for clients/UI.
    transcript_from_url: bool = False


class VideoListResponse(BaseModel):
    items: list[VideoOut]
    limit: int


class PlaylistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    playlist_position: int
    youtube_video_id: str
    video_id: uuid.UUID | None = None
    state: str


class PlaylistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    youtube_playlist_id: str
    title: str
    status: str
    total_items: int
    items: list[PlaylistItemOut] = Field(default_factory=list)
    coverage: dict[str, int] | None = None
    transcript_from_url: bool = False


class PlaylistImportResponse(BaseModel):
    playlist: PlaylistOut
    created: bool
    truncated: bool
    notices: list[ImportNoticeOut]
    transcript_from_url: bool = False


class ModelCapabilitiesOut(BaseModel):
    supports_json_schema: bool
    supports_stream: bool
    supports_vision: bool
    supports_batch: bool
    max_context_tokens: int


class ChatProviderSettingsOut(BaseModel):
    provider: str
    model: str
    key_configured: bool
    capabilities: ModelCapabilitiesOut
    allowlisted_providers: list[str]
    allowlisted_models: list[str]


class EmbeddingProviderSettingsOut(BaseModel):
    provider: str
    model: str
    dimensions: int
    profile_id: str
    key_configured: bool
    capabilities: ModelCapabilitiesOut
    allowlisted_providers: list[str]
    allowlisted_models: list[str]
    deepseek_embeddings_supported: bool = False


class ProviderLimitsOut(BaseModel):
    request_timeout_seconds: int
    max_output_tokens: int
    max_input_characters: int
    max_retries: int


class ProviderSettingsResponse(BaseModel):
    """Public provider configuration — never includes API keys or secret material."""

    chat: ChatProviderSettingsOut
    embeddings: EmbeddingProviderSettingsOut
    limits: ProviderLimitsOut


class TranscriptUploadAccepted(BaseModel):
    """202 response for authorized transcript ingestion."""

    job_id: uuid.UUID
    status: str
    stage: str
    percent: int
    source_asset_id: uuid.UUID | None = None
    source_revision: int | None = None
    timecode_quality: str | None = None
    replay: bool = False


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    video_id: uuid.UUID | None = None
    source_asset_id: uuid.UUID | None = None
    job_type: str
    status: str
    stage: str
    attempt: int
    percent: int
    last_error_code: str | None = None
    result_resource_id: uuid.UUID | None = None


class TranscriptSegmentOut(BaseModel):
    """Sanitized segment for UI — text is markup-stripped; never raw HTML."""

    id: uuid.UUID
    ordinal: int
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    content_hash: str


class SourceAssetOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    source_kind: str
    content_hash: str
    timecode_quality: str
    source_revision: int
    rights_attested_at: datetime | None = None
    segments: list[TranscriptSegmentOut] = Field(default_factory=list)


class ChapterOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    workspace_id: uuid.UUID
    source_revision: int
    title: str
    start_segment_id: uuid.UUID | None = None
    end_segment_id: uuid.UUID | None = None
    topic_json: dict[str, Any] | None = None


class ChapterListResponse(BaseModel):
    items: list[ChapterOut]
    source_revision: int | None = None


class SummaryClaimOut(BaseModel):
    text: str
    evidence_segment_ids: list[str] = Field(default_factory=list)
    provenance: str = "source_supported"


class SummaryExampleOut(BaseModel):
    text: str
    origin: str = "ai_generated_illustration"


class SummaryOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    scope_kind: str
    scope_id: uuid.UUID
    summary_kind: str
    revision: int
    status: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    claims: list[SummaryClaimOut] = Field(default_factory=list)
    examples: list[SummaryExampleOut] = Field(default_factory=list)
    evidence_segment_ids: list[str] = Field(default_factory=list)
    origin: str | None = None
    coverage_json: dict[str, Any] | None = None
    provider_run_id: uuid.UUID | None = None
    cache_hit: bool = False


class SummaryListResponse(BaseModel):
    items: list[SummaryOut]
    blocked: bool = False
    source_revision: int | None = None


class SummarizeAccepted(BaseModel):
    video_id: uuid.UUID
    chapter_count: int
    summary_count: int
    cache_hits: int
    provider_calls: int
    blocked: bool
    source_revision: int
