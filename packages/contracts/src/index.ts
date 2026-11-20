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
  scope_kind: "video" | "chapter" | "chunk" | string;
  scope_id: string;
  summary_kind: SummaryKind | string;
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

export interface ScaffoldMeta {
  phase: "06";
  operationalEndpoints: true;
  youtubeMetadataImport: true;
  authorizedTranscriptIngest: true;
  durableJobs: true;
  chaptersAndSummaries: true;
}
