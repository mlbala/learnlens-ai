/**
 * Shared contract types.
 * Phase 05 adds authorized transcript upload + job status shapes.
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

export interface ScaffoldMeta {
  phase: "05";
  operationalEndpoints: true;
  youtubeMetadataImport: true;
  authorizedTranscriptIngest: true;
  durableJobs: true;
}
