/**
 * Shared contract types.
 * Phase 04 adds YouTube metadata import shapes (no transcript access from URL alone).
 */

export type ProviderKind = "fake" | "openai" | "gemini" | "deepseek";

export type YoutubeMetadataProvider = "fake" | "youtube" | "youtube_data_api" | "official";

export type VideoImportStatus =
  | "metadata_only"
  | "needs_transcript"
  | "unavailable"
  | "fixture";

export interface ImportNotice {
  code: string;
  message: string;
}

export interface VideoImportContract {
  transcript_from_url: false;
  status: VideoImportStatus | string;
  notices: ImportNotice[];
}

export interface ScaffoldMeta {
  phase: "04";
  operationalEndpoints: true;
  youtubeMetadataImport: true;
}
