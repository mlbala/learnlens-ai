/**
 * Shared contract types.
 * Phase 06 adds chapter + hierarchical summary shapes.
 */

export type ProviderKind = "fake" | "openai" | "gemini" | "deepseek";

export type YoutubeMetadataProvider = "fake" | "youtube" | "youtube_data_api" | "official";

export type VideoImportStatus =
  | "metadata_only"
  | "needs_transcript"
  | "unavailable"
  | "fixture"
  | "ready"
  | "validating"
  | "failed";

export type TranscriptSourceKind = "srt" | "vtt" | "txt" | "paste";

export type TimecodeQuality = "original" | "none" | "unknown";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export type JobStage =
  | "pending"
  | "validating"
  | "persisting"
  | "segmenting"
  | "complete"
  | "error"
  | "metadata";

export type SummaryKind = "short" | "detailed" | "simple" | "technical";

export type ExplanationMode = "simple" | "standard" | "technical";

export type ChatScopeKind = "video" | "playlist" | "library";

export type Provenance =
  | "source_supported"
  | "ai_generated_illustration"
  | "inference_or_interpretation"
  | "not_covered";

export interface ImportNotice {
  code: string;
  message: string;
}

export interface VideoImportContract {
  transcript_from_url: false;
  status: VideoImportStatus | string;
  notices: ImportNotice[];
}

export interface TranscriptUploadAccepted {
  job_id: string;
  status: JobStatus | string;
  stage: JobStage | string;
  percent: number;
  source_asset_id?: string | null;
  source_revision?: number | null;
  timecode_quality?: TimecodeQuality | string | null;
  replay: boolean;
}

export interface JobStatusContract {
  id: string;
  workspace_id: string;
  video_id?: string | null;
  source_asset_id?: string | null;
  job_type: string;
  status: JobStatus | string;
  stage: JobStage | string;
  attempt: number;
  percent: number;
  last_error_code?: string | null;
}

export interface ChapterContract {
  id: string;
  video_id: string;
  workspace_id: string;
  source_revision: number;
  title: string;
  start_segment_id?: string | null;
  end_segment_id?: string | null;
  topic_json?: Record<string, unknown> | null;
}

export interface SummaryClaimContract {
  text: string;
  evidence_segment_ids: string[];
  provenance: Provenance | string;
}

export interface SummaryExampleContract {
  text: string;
  origin: "ai_generated_illustration" | "source_supported" | string;
}

export interface SummaryContract {
  id: string;
  workspace_id: string;
  scope_kind: "video" | "chapter" | "chunk" | "playlist" | string;
  scope_id: string;
  summary_kind: SummaryKind | "course" | string;
  revision: number;
  status: "ready" | "blocked" | "failed" | string;
  summary: string;
  key_points: string[];
  claims: SummaryClaimContract[];
  examples: SummaryExampleContract[];
  evidence_segment_ids: string[];
  origin?: string | null;
  coverage_json?: Record<string, unknown> | null;
  provider_run_id?: string | null;
}

export interface PlaylistCourseSummaryContract {
  id: string;
  workspace_id: string;
  playlist_id: string;
  summary_kind: "course" | string;
  status: string;
  coverage_label: "partial" | "complete" | string;
  coverage_ratio: number;
  included_count: number;
  excluded_count: number;
  total_count: number;
  included_video_ids: string[];
  excluded_video_ids: string[];
  source_revisions: Record<string, number>;
  caveat?: string | null;
  overview: string;
  topic_modules: Array<{
    title: string;
    summary: string;
    video_ids: string[];
    evidence_segment_ids: string[];
  }>;
  learning_map: Array<{ label: string; video_ids: string[]; order: number }>;
  cross_video_concepts: Array<{
    name: string;
    description: string;
    video_ids: string[];
    evidence_segment_ids: string[];
  }>;
  redundant_topics: Array<{ topic: string; video_ids: string[]; note: string }>;
  key_takeaways: Array<{
    text: string;
    source_video_ids: string[];
    evidence_segment_ids: string[];
    provenance: Provenance | string;
  }>;
  origin?: string | null;
  cache_hit?: boolean;
  video_cache_hits?: number;
}

export interface QaClaimContract {
  text: string;
  citation_segment_ids: string[];
}

export interface QaAnalogyContract {
  text: string;
  origin: "ai_generated_illustration" | string;
}

export interface CitationContract {
  citation_id: string;
  video_id: string;
  video_title: string;
  segment_id: string;
  snippet: string;
  start_ms?: number | null;
  end_ms?: number | null;
  youtube_url?: string | null;
  timing_verified: boolean;
}

export interface ChatThreadContract {
  id: string;
  workspace_id: string;
  scope_kind: ChatScopeKind | string;
  scope_id?: string | null;
  title?: string | null;
  created_by: string;
}

export interface ChatMessageContract {
  id: string;
  thread_id: string;
  workspace_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  explanation_mode?: ExplanationMode | string | null;
  confidence_label?: string | null;
  unsupported: boolean;
  claims: QaClaimContract[];
  analogies: QaAnalogyContract[];
  citations: CitationContract[];
  provider_run_id?: string | null;
}

export type PresentationLanguage = "en" | "ta";

export type StudyItemKind = "flashcard" | "quiz";

export interface TutorEvidenceContract {
  segment_id: string;
  snippet: string;
  start_ms?: number | null;
  end_ms?: number | null;
  youtube_url?: string | null;
  timing_verified: boolean;
}

export interface StudyItemContract {
  id: string;
  deck_id: string;
  item_kind: StudyItemKind | string;
  ordinal: number;
  prompt: string;
  answer: string;
  explanation: string;
  explanation_origin: Provenance | string;
  choices: string[];
  correct_choice_index?: number | null;
  evidence_segment_ids: string[];
  evidence: TutorEvidenceContract[];
  presentation?: Record<string, { prompt?: string; answer?: string; explanation?: string }>;
  concept_id?: string | null;
}

export interface StudyDeckContract {
  id: string;
  workspace_id: string;
  user_id: string;
  video_id: string;
  title: string;
  presentation_language: PresentationLanguage | string;
  source_revision: number;
  status: string;
  origin: string;
  items: StudyItemContract[];
  disclaimer: string;
}

export interface ScaffoldMeta {
  phase: "18";
  operationalEndpoints: true;
  youtubeMetadataImport: true;
  authorizedTranscriptIngest: true;
  durableJobs: true;
  chaptersAndSummaries: true;
  groundedQa: true;
  libraryScreens: true;
  lessonReaderAndChat: true;
  playlistSynthesis: true;
  tutorQuizGraph: true;
}

export interface PlaylistCoverageContract {
  total: number;
  ready: number;
  needs_transcript: number;
  unavailable: number;
  failed: number;
  missing?: number;
}
