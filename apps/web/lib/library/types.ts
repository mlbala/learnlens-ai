/**
 * Library screen contracts aligned with apps/api schemas + packages/contracts.
 * Fixture-safe; never invents transcript access from a URL alone.
 */

export type LibraryItemKind = "video" | "playlist";

export type ImportNotice = {
  code: string;
  message: string;
};

export type PlaylistCoverage = {
  total: number;
  ready: number;
  needs_transcript: number;
  unavailable: number;
  failed: number;
  /** Items that are not ready for any reason (derived). */
  missing: number;
};

export type VideoRecord = {
  id: string;
  workspace_id: string;
  youtube_video_id: string;
  title: string;
  status: string;
  channel_title?: string | null;
  duration_seconds?: number | null;
  source_url?: string | null;
  transcript_access: boolean;
  coverage?: string | null;
  fixture_data?: boolean;
  metadata_json?: Record<string, unknown> | null;
};

export type PlaylistItemRecord = {
  id: string;
  playlist_position: number;
  youtube_video_id: string;
  video_id?: string | null;
  state: string;
  title?: string | null;
  duration_seconds?: number | null;
  channel_title?: string | null;
};

export type PlaylistRecord = {
  id: string;
  workspace_id: string;
  youtube_playlist_id: string;
  title: string;
  status: string;
  total_items: number;
  channel_title?: string | null;
  items: PlaylistItemRecord[];
  coverage: PlaylistCoverage;
  transcript_from_url: false;
  fixture_data?: boolean;
};

export type PlaylistSummary = {
  id: string;
  workspace_id: string;
  youtube_playlist_id: string;
  title: string;
  status: string;
  total_items: number;
  channel_title?: string | null;
  coverage: PlaylistCoverage;
  fixture_data?: boolean;
};

export type VideoImportResult = {
  video: VideoRecord;
  created: boolean;
  notices: ImportNotice[];
  companion_playlist_id?: string | null;
  transcript_from_url: false;
};

export type PlaylistImportResult = {
  playlist: PlaylistRecord;
  created: boolean;
  truncated: boolean;
  notices: ImportNotice[];
  transcript_from_url: false;
};

export type TranscriptUploadResult = {
  job_id: string;
  status: string;
  stage: string;
  percent: number;
  source_asset_id?: string | null;
  source_revision?: number | null;
  timecode_quality?: string | null;
  replay: boolean;
};

export type JobRecord = {
  id: string;
  workspace_id: string;
  video_id?: string | null;
  source_asset_id?: string | null;
  job_type: string;
  status: string;
  stage: string;
  attempt: number;
  percent: number;
  last_error_code?: string | null;
};

export type LibraryListPage<T> = {
  items: T[];
  next_cursor: string | null;
  limit: number;
  mode: "fixture" | "api";
};

export type DashboardStats = {
  videos_ready: number;
  playlists: number;
  processing: number;
  pending_transcripts: number;
  jobs_needing_attention: number;
  mode: "fixture" | "api";
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    request_id?: string;
    details?: Record<string, unknown>;
  };
};

export class LibraryApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId?: string;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.name = "LibraryApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export type TranscriptUploadInput = {
  videoId: string;
  rightsAttested: boolean;
  sourceKind: "srt" | "vtt" | "txt" | "paste";
  pasteText?: string;
  file?: File;
};
