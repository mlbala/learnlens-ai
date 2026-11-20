/**
 * Typed library API client — fixture demo by default; HTTP when mode=api.
 * No paid providers; never claims transcript_from_url.
 */

import { normalizeCoverage } from "@/lib/library/coverage";
import {
  FIXTURE_PLAYLIST,
  FIXTURE_VIDEOS,
  FIXTURE_WORKSPACE_ID,
  cloneFixtureJob,
  fixtureDashboardStats,
  fixturePlaylistSummary,
} from "@/lib/library/fixtures";
import { parseSourceUrl } from "@/lib/library/url";
import type {
  DashboardStats,
  JobRecord,
  LibraryListPage,
  PlaylistImportResult,
  PlaylistRecord,
  PlaylistSummary,
  TranscriptUploadInput,
  TranscriptUploadResult,
  VideoImportResult,
  VideoRecord,
} from "@/lib/library/types";
import { LibraryApiError } from "@/lib/library/types";

export type LibraryClientMode = "fixture" | "api";

export type ListParams = {
  cursor?: string | null;
  limit?: number;
  status?: string | null;
  q?: string | null;
};

export interface LibraryClient {
  readonly mode: LibraryClientMode;
  getDashboard(): Promise<DashboardStats>;
  listVideos(params?: ListParams): Promise<LibraryListPage<VideoRecord>>;
  getVideo(videoId: string): Promise<VideoRecord>;
  listPlaylists(params?: ListParams): Promise<LibraryListPage<PlaylistSummary>>;
  getPlaylist(playlistId: string): Promise<PlaylistRecord>;
  importSource(
    youtubeUrl: string,
    opts?: { preferPlaylist?: boolean },
  ): Promise<{ kind: "video"; result: VideoImportResult } | { kind: "playlist"; result: PlaylistImportResult }>;
  uploadTranscript(input: TranscriptUploadInput): Promise<TranscriptUploadResult>;
  getJob(jobId: string): Promise<JobRecord>;
}

function pageSlice<T>(
  items: T[],
  params: ListParams | undefined,
  mode: LibraryClientMode,
): LibraryListPage<T> {
  const limit = Math.min(Math.max(params?.limit ?? 12, 1), 50);
  const start = params?.cursor ? Number.parseInt(params.cursor, 10) : 0;
  const offset = Number.isFinite(start) && start > 0 ? start : 0;
  const slice = items.slice(offset, offset + limit);
  const next = offset + limit < items.length ? String(offset + limit) : null;
  return { items: slice, next_cursor: next, limit, mode };
}

function matchesQuery(title: string, q?: string | null): boolean {
  if (!q?.trim()) return true;
  return title.toLowerCase().includes(q.trim().toLowerCase());
}

function statusFilter(status: string, filter?: string | null): boolean {
  if (!filter || filter === "all") return true;
  if (filter === "ready") return status === "ready";
  if (filter === "needs_transcript") {
    return status === "needs_transcript" || status === "metadata_only";
  }
  if (filter === "processing") {
    return ["queued", "processing", "validating", "segmenting", "summarizing", "indexing"].includes(
      status,
    );
  }
  if (filter === "failed") {
    return ["failed", "failed_retryable", "failed_terminal"].includes(status);
  }
  return status === filter;
}

/** In-memory mutable fixture store for import/upload demos. */
export class FixtureLibraryClient implements LibraryClient {
  readonly mode = "fixture" as const;
  private videos: VideoRecord[];
  private playlist: PlaylistRecord;
  private jobs = new Map<string, JobRecord>();

  constructor() {
    this.videos = structuredClone(FIXTURE_VIDEOS);
    this.playlist = structuredClone(FIXTURE_PLAYLIST);
  }

  async getDashboard(): Promise<DashboardStats> {
    return fixtureDashboardStats(this.videos);
  }

  async listVideos(params?: ListParams): Promise<LibraryListPage<VideoRecord>> {
    const filtered = this.videos.filter(
      (v) => matchesQuery(v.title, params?.q) && statusFilter(v.status, params?.status),
    );
    return pageSlice(filtered, params, "fixture");
  }

  async getVideo(videoId: string): Promise<VideoRecord> {
    const found = this.videos.find((v) => v.id === videoId);
    if (!found) {
      throw new LibraryApiError(404, "NOT_FOUND", "Video not found in fixture library.");
    }
    return found;
  }

  async listPlaylists(params?: ListParams): Promise<LibraryListPage<PlaylistSummary>> {
    const summary = fixturePlaylistSummary();
    summary.coverage = this.playlist.coverage;
    summary.status = this.playlist.status;
    summary.total_items = this.playlist.total_items;
    const items = matchesQuery(summary.title, params?.q) ? [summary] : [];
    return pageSlice(items, params, "fixture");
  }

  async getPlaylist(playlistId: string): Promise<PlaylistRecord> {
    if (playlistId !== this.playlist.id && playlistId !== this.playlist.youtube_playlist_id) {
      throw new LibraryApiError(404, "NOT_FOUND", "Playlist not found in fixture library.");
    }
    return this.playlist;
  }

  async importSource(
    youtubeUrl: string,
    opts?: { preferPlaylist?: boolean },
  ): Promise<
    { kind: "video"; result: VideoImportResult } | { kind: "playlist"; result: PlaylistImportResult }
  > {
    const parsed = parseSourceUrl(youtubeUrl);
    if (!parsed.ok) {
      throw new LibraryApiError(422, parsed.error.code, parsed.error.message);
    }

    if (parsed.value.kind === "playlist" || (opts?.preferPlaylist && parsed.value.kind === "video" && parsed.value.companionPlaylistId)) {
      const playlistId =
        parsed.value.kind === "playlist"
          ? parsed.value.playlistId
          : parsed.value.companionPlaylistId!;
      if (playlistId !== this.playlist.youtube_playlist_id) {
        throw new LibraryApiError(
          404,
          "NOT_FOUND",
          "Unknown fixture playlist. Try https://www.youtube.com/playlist?list=PLfixtureCourse01",
        );
      }
      return {
        kind: "playlist",
        result: {
          playlist: this.playlist,
          created: false,
          truncated: false,
          notices: [
            {
              code: "FIXTURE_DATA",
              message: "Replayed synthetic fixture playlist — not live YouTube data.",
            },
            {
              code: "SOURCE_TRANSCRIPT_REQUIRED",
              message: "A URL alone never grants transcript access.",
            },
          ],
          transcript_from_url: false,
        },
      };
    }

    const videoId = parsed.value.kind === "video" ? parsed.value.videoId : "";
    let existing = this.videos.find((v) => v.youtube_video_id === videoId);
    let created = false;
    if (!existing) {
      if (!videoId.startsWith("vid")) {
        throw new LibraryApiError(
          404,
          "NOT_FOUND",
          "Unknown fixture video. Try https://www.youtube.com/watch?v=vidPublic01",
        );
      }
      existing = {
        id: crypto.randomUUID(),
        workspace_id: FIXTURE_WORKSPACE_ID,
        youtube_video_id: videoId,
        title: `Fixture import ${videoId} (synthetic)`,
        status: "needs_transcript",
        channel_title: "LearnLens Fixtures",
        duration_seconds: null,
        source_url: parsed.value.kind === "video" ? parsed.value.canonicalUrl : null,
        transcript_access: false,
        coverage: "metadata_only",
        fixture_data: true,
        metadata_json: { fixture_data: true },
      };
      this.videos = [existing, ...this.videos];
      created = true;
    }

    return {
      kind: "video",
      result: {
        video: existing,
        created,
        notices: [
          {
            code: "FIXTURE_DATA",
            message: "Synthetic fixture metadata only — not a real YouTube transcript.",
          },
          {
            code: "SOURCE_TRANSCRIPT_REQUIRED",
            message: "Upload a permitted transcript to study this video.",
          },
        ],
        companion_playlist_id:
          parsed.value.kind === "video" ? parsed.value.companionPlaylistId ?? null : null,
        transcript_from_url: false,
      },
    };
  }

  async uploadTranscript(input: TranscriptUploadInput): Promise<TranscriptUploadResult> {
    if (!input.rightsAttested) {
      throw new LibraryApiError(
        422,
        "ATTESTATION_REQUIRED",
        "Confirm you own this transcript or have permission to process it.",
      );
    }
    const video = await this.getVideo(input.videoId);
    if (video.status === "unavailable") {
      throw new LibraryApiError(
        422,
        "VIDEO_UNAVAILABLE",
        "Cannot attach a transcript to an unavailable video.",
      );
    }
    if (input.sourceKind === "paste" && !input.pasteText?.trim()) {
      throw new LibraryApiError(422, "EMPTY_TRANSCRIPT", "Paste transcript text is required.");
    }
    if (input.sourceKind !== "paste" && !input.file && !input.pasteText?.trim()) {
      throw new LibraryApiError(422, "EMPTY_TRANSCRIPT", "Upload a file or paste transcript text.");
    }

    const job = cloneFixtureJob(video.id, {
      status: "running",
      stage: "validating",
      percent: 15,
    });
    this.jobs.set(job.id, job);

    // Simulate durable progression without inventing YouTube captions.
    queueMicrotask(() => {
      const mid: JobRecord = {
        ...job,
        status: "running",
        stage: "persisting",
        percent: 55,
      };
      this.jobs.set(job.id, mid);
      queueMicrotask(() => {
        const done: JobRecord = {
          ...job,
          status: "succeeded",
          stage: "complete",
          percent: 100,
        };
        this.jobs.set(job.id, done);
        const idx = this.videos.findIndex((v) => v.id === video.id);
        if (idx >= 0) {
          const updated: VideoRecord = {
            ...this.videos[idx]!,
            status: "ready",
            transcript_access: true,
            coverage: "ready",
            metadata_json: {
              ...(this.videos[idx]!.metadata_json ?? {}),
              fixture_data: true,
              fixture_transcript: true,
            },
          };
          this.videos = [
            ...this.videos.slice(0, idx),
            updated,
            ...this.videos.slice(idx + 1),
          ];
          this.playlist = {
            ...this.playlist,
            items: this.playlist.items.map((item) =>
              item.video_id === video.id ? { ...item, state: "ready" } : item,
            ),
            coverage: recomputeCoverage(
              this.playlist.items.map((item) =>
                item.video_id === video.id ? { ...item, state: "ready" } : item,
              ),
            ),
          };
        }
      });
    });

    return {
      job_id: job.id,
      status: job.status,
      stage: job.stage,
      percent: job.percent,
      timecode_quality: input.sourceKind === "txt" || input.sourceKind === "paste" ? "none" : "original",
      replay: false,
    };
  }

  async getJob(jobId: string): Promise<JobRecord> {
    const job = this.jobs.get(jobId);
    if (!job) {
      throw new LibraryApiError(404, "NOT_FOUND", "Job not found in fixture store.");
    }
    return job;
  }
}

function recomputeCoverage(
  items: PlaylistRecord["items"],
): PlaylistRecord["coverage"] {
  const counts = { ready: 0, needs_transcript: 0, unavailable: 0, failed: 0 };
  for (const item of items) {
    if (item.state === "ready") counts.ready += 1;
    else if (item.state === "needs_transcript") counts.needs_transcript += 1;
    else if (item.state === "unavailable") counts.unavailable += 1;
    else if (item.state === "failed" || item.state === "failed_retryable") counts.failed += 1;
    else counts.needs_transcript += 1;
  }
  return normalizeCoverage({ total: items.length, ...counts });
}

export class HttpLibraryClient implements LibraryClient {
  readonly mode = "api" as const;

  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });
    const body = (await res.json().catch(() => null)) as
      | T
      | { error?: { code?: string; message?: string; request_id?: string } }
      | null;
    if (!res.ok) {
      const err = body && typeof body === "object" && "error" in body ? body.error : undefined;
      throw new LibraryApiError(
        res.status,
        err?.code ?? "HTTP_ERROR",
        err?.message ?? `Request failed (${res.status})`,
        err?.request_id,
      );
    }
    return body as T;
  }

  async getDashboard(): Promise<DashboardStats> {
    const videos = await this.listVideos({ limit: 100 });
    const playlists = await this.listPlaylists({ limit: 100 });
    return {
      videos_ready: videos.items.filter((v) => v.status === "ready").length,
      playlists: playlists.items.length,
      processing: videos.items.filter((v) =>
        ["queued", "processing", "validating", "segmenting"].includes(v.status),
      ).length,
      pending_transcripts: videos.items.filter((v) =>
        ["needs_transcript", "metadata_only"].includes(v.status),
      ).length,
      jobs_needing_attention: videos.items.filter((v) =>
        ["failed_retryable", "failed", "failed_terminal"].includes(v.status),
      ).length,
      mode: "api",
    };
  }

  async listVideos(params?: ListParams): Promise<LibraryListPage<VideoRecord>> {
    const qs = new URLSearchParams();
    qs.set("limit", String(params?.limit ?? 50));
    if (params?.status) qs.set("status", params.status);
    const data = await this.request<{ items: VideoRecord[]; limit: number }>(
      `/api/v1/videos?${qs.toString()}`,
    );
    let items = data.items.map((v) => ({
      ...v,
      fixture_data: Boolean(v.metadata_json && (v.metadata_json as { fixture_data?: boolean }).fixture_data),
    }));
    if (params?.q) {
      items = items.filter((v) => matchesQuery(v.title, params.q));
    }
    return { items, next_cursor: null, limit: data.limit, mode: "api" };
  }

  async getVideo(videoId: string): Promise<VideoRecord> {
    return this.request<VideoRecord>(`/api/v1/videos/${videoId}`);
  }

  async listPlaylists(params?: ListParams): Promise<LibraryListPage<PlaylistSummary>> {
    const qs = new URLSearchParams();
    qs.set("limit", String(params?.limit ?? 50));
    const data = await this.request<{
      items: Array<PlaylistSummary & { coverage?: Record<string, number> | null }>;
      limit: number;
    }>(`/api/v1/playlists?${qs.toString()}`);
    let items = data.items.map((p) => ({
      ...p,
      coverage: normalizeCoverage(p.coverage, p.total_items),
      fixture_data: p.fixture_data ?? false,
    }));
    if (params?.q) {
      items = items.filter((p) => matchesQuery(p.title, params.q));
    }
    return { items, next_cursor: null, limit: data.limit, mode: "api" };
  }

  async getPlaylist(playlistId: string): Promise<PlaylistRecord> {
    const data = await this.request<
      PlaylistRecord & { coverage?: Record<string, number> | null; transcript_from_url?: boolean }
    >(`/api/v1/playlists/${playlistId}`);
    return {
      ...data,
      transcript_from_url: false,
      coverage: normalizeCoverage(data.coverage, data.total_items),
    };
  }

  async importSource(
    youtubeUrl: string,
    opts?: { preferPlaylist?: boolean },
  ): Promise<
    { kind: "video"; result: VideoImportResult } | { kind: "playlist"; result: PlaylistImportResult }
  > {
    const parsed = parseSourceUrl(youtubeUrl);
    if (!parsed.ok) {
      throw new LibraryApiError(422, parsed.error.code, parsed.error.message);
    }
    const csrf = readCookie("ll_csrf");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    };
    if (csrf) headers["X-CSRF-Token"] = csrf;

    const usePlaylist =
      parsed.value.kind === "playlist" ||
      Boolean(
        opts?.preferPlaylist &&
          parsed.value.kind === "video" &&
          parsed.value.companionPlaylistId,
      );

    if (usePlaylist) {
      const url =
        parsed.value.kind === "playlist"
          ? parsed.value.canonicalUrl
          : `https://www.youtube.com/playlist?list=${parsed.value.companionPlaylistId}`;
      const result = await this.request<PlaylistImportResult>("/api/v1/playlists/import", {
        method: "POST",
        headers,
        body: JSON.stringify({ youtube_url: url }),
      });
      return {
        kind: "playlist",
        result: {
          ...result,
          transcript_from_url: false,
          playlist: {
            ...result.playlist,
            transcript_from_url: false,
            coverage: normalizeCoverage(result.playlist.coverage, result.playlist.total_items),
          },
        },
      };
    }

    const result = await this.request<VideoImportResult>("/api/v1/videos/import", {
      method: "POST",
      headers,
      body: JSON.stringify({
        youtube_url:
          parsed.value.kind === "video" ? parsed.value.canonicalUrl : youtubeUrl,
      }),
    });
    return { kind: "video", result: { ...result, transcript_from_url: false } };
  }

  async uploadTranscript(input: TranscriptUploadInput): Promise<TranscriptUploadResult> {
    if (!input.rightsAttested) {
      throw new LibraryApiError(
        422,
        "ATTESTATION_REQUIRED",
        "Confirm you own this transcript or have permission to process it.",
      );
    }
    const csrf = readCookie("ll_csrf");
    const form = new FormData();
    form.set("rights_attested", "true");
    form.set("source_kind", input.sourceKind);
    if (input.pasteText) form.set("paste_text", input.pasteText);
    if (input.file) form.set("file", input.file);

    const headers: Record<string, string> = {
      "Idempotency-Key": crypto.randomUUID(),
    };
    if (csrf) headers["X-CSRF-Token"] = csrf;

    return this.request<TranscriptUploadResult>(`/api/v1/videos/${input.videoId}/transcripts`, {
      method: "POST",
      headers,
      body: form,
    });
  }

  async getJob(jobId: string): Promise<JobRecord> {
    return this.request<JobRecord>(`/api/v1/jobs/${jobId}`);
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

let singleton: LibraryClient | null = null;

export function resolveLibraryMode(): LibraryClientMode {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_LIBRARY_MODE === "api") {
    return "api";
  }
  return "fixture";
}

export function getLibraryClient(): LibraryClient {
  if (singleton) return singleton;
  const mode = resolveLibraryMode();
  singleton = mode === "api" ? new HttpLibraryClient("") : new FixtureLibraryClient();
  return singleton;
}

/** Test helper — reset singleton between Vitest cases. */
export function resetLibraryClient(client?: LibraryClient): void {
  singleton = client ?? null;
}
