/**
 * Typed library API client — fixture demo by default; HTTP when mode=api.
 * No paid providers; never claims transcript_from_url.
 */

import { isOfficialYoutubeId } from "@/lib/lesson/citations";
import { toLessonTitle } from "@/lib/lesson/title";
import { normalizeCoverage } from "@/lib/library/coverage";
import {
  FIXTURE_PLAYLIST,
  FIXTURE_VIDEOS,
  FIXTURE_WORKSPACE_ID,
  cloneFixtureJob,
  fixtureDashboardStats,
  fixturePlaylistCourseSummary,
  fixturePlaylistSummary,
} from "@/lib/library/fixtures";
import { parseSourceUrl } from "@/lib/library/url";
import type {
  DashboardStats,
  JobRecord,
  LibraryListPage,
  PlaylistCourseSummary,
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
  getPlaylistCourseSummary(playlistId: string): Promise<PlaylistCourseSummary>;
  synthesizePlaylist(playlistId: string): Promise<JobRecord>;
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

type SavedLessonSegment = {
  id: string;
  ordinal: number;
  text: string;
  content_hash: string;
  start_ms: number | null;
  end_ms: number | null;
};

type SavedLessonSummary = {
  id: string;
  workspace_id: string;
  youtube_video_id: string;
  title: string;
  status: string;
  channel_title?: string | null;
  duration_seconds?: number | null;
  source_url?: string | null;
  summary?: string;
  key_points?: string[];
};

type SavedLessonDetail = {
  video: VideoRecord;
  summary: string;
  key_points: string[];
  segments: SavedLessonSegment[];
  created?: boolean;
};

function summaryToVideo(item: SavedLessonSummary): VideoRecord {
  return {
    id: item.id,
    workspace_id: item.workspace_id,
    youtube_video_id: item.youtube_video_id,
    title: item.title,
    status: item.status,
    channel_title: item.channel_title ?? null,
    duration_seconds: item.duration_seconds ?? null,
    source_url: item.source_url ?? null,
    transcript_access: true,
    coverage: "ready",
    fixture_data: false,
    metadata_json: {
      fixture_data: false,
      gemini_lesson: {
        summary: item.summary ?? "",
        key_points: item.key_points ?? [],
        transcript: "",
      },
    },
  };
}

function detailToVideo(body: SavedLessonDetail): VideoRecord {
  const transcript = body.segments.map((segment) => segment.text).join("\n\n");
  return {
    ...body.video,
    transcript_access: true,
    coverage: body.video.coverage ?? "ready",
    fixture_data: false,
    metadata_json: {
      ...(body.video.metadata_json ?? {}),
      fixture_data: false,
      gemini_lesson: {
        summary: body.summary,
        key_points: body.key_points,
        transcript,
      },
      gemini_segments: body.segments,
    },
  };
}

async function readLibraryError(res: Response, fallback: string): Promise<LibraryApiError> {
  const body = (await res.json().catch(() => null)) as {
    error?: { code?: string; message?: string; request_id?: string };
  } | null;
  return new LibraryApiError(
    res.status,
    body?.error?.code ?? "HTTP_ERROR",
    body?.error?.message ?? fallback,
    body?.error?.request_id,
  );
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

  private readonly seedDemo: boolean;

  constructor(options?: { seedDemo?: boolean }) {
    this.seedDemo = options?.seedDemo ?? true;
    this.videos = this.seedDemo ? structuredClone(FIXTURE_VIDEOS) : [];
    this.playlist = structuredClone(FIXTURE_PLAYLIST);
  }

  private remember(video: VideoRecord): void {
    this.videos = [
      video,
      ...this.videos.filter(
        (item) => item.id !== video.id && item.youtube_video_id !== video.youtube_video_id,
      ),
    ];
  }

  private async refreshSavedLessons(): Promise<void> {
    const res = await fetch("/api/learning-history", { credentials: "include", cache: "no-store" });
    if (!res.ok) {
      throw await readLibraryError(res, "Could not load saved lessons.");
    }
    const body = (await res.json()) as { items?: SavedLessonSummary[] };
    this.videos = (body.items ?? []).map(summaryToVideo);
  }

  private async openSavedLesson(videoId: string): Promise<VideoRecord> {
    const res = await fetch(`/api/learning-history/${videoId}/open`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) {
      throw await readLibraryError(res, "Could not open the saved lesson.");
    }
    const body = (await res.json()) as SavedLessonDetail;
    const video = detailToVideo(body);
    this.remember(video);
    return video;
  }

  private async persistLesson(input: {
    videoId: string;
    title: string;
    channelTitle: string | null;
    summary: string;
    keyPoints: string[];
    transcript: string;
    sourceUrl: string;
  }): Promise<{ video: VideoRecord; created: boolean }> {
    const res = await fetch("/api/learning-history", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        youtube_video_id: input.videoId,
        title: input.title,
        channel_title: input.channelTitle,
        summary: input.summary,
        key_points: input.keyPoints,
        transcript: input.transcript,
        source_url: input.sourceUrl,
      }),
    });
    if (!res.ok) {
      throw await readLibraryError(res, "Could not save this lesson.");
    }
    const body = (await res.json()) as SavedLessonDetail;
    const video = detailToVideo(body);
    this.remember(video);
    return { video, created: Boolean(body.created) };
  }

  async getDashboard(): Promise<DashboardStats> {
    if (!this.seedDemo) {
      await this.refreshSavedLessons();
    }
    return fixtureDashboardStats(this.videos);
  }

  async listVideos(params?: ListParams): Promise<LibraryListPage<VideoRecord>> {
    if (!this.seedDemo) {
      await this.refreshSavedLessons();
    }
    const filtered = this.videos.filter(
      (v) => matchesQuery(v.title, params?.q) && statusFilter(v.status, params?.status),
    );
    return pageSlice(filtered, params, "fixture");
  }

  async getVideo(videoId: string): Promise<VideoRecord> {
    if (!this.seedDemo) {
      return this.openSavedLesson(videoId);
    }
    const found = this.videos.find((v) => v.id === videoId);
    if (!found) {
      throw new LibraryApiError(404, "NOT_FOUND", "Video not found in fixture library.");
    }
    return found;
  }

  async listPlaylists(params?: ListParams): Promise<LibraryListPage<PlaylistSummary>> {
    if (!this.seedDemo) {
      return pageSlice([], params, "fixture");
    }
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

  async getPlaylistCourseSummary(playlistId: string): Promise<PlaylistCourseSummary> {
    await this.getPlaylist(playlistId);
    return fixturePlaylistCourseSummary(this.playlist.id);
  }

  async synthesizePlaylist(playlistId: string): Promise<JobRecord> {
    await this.getPlaylist(playlistId);
    return cloneFixtureJob(playlistId, {
      job_type: "playlist_synthesis",
      status: "succeeded",
      stage: "complete",
      percent: 100,
    });
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
    if (!this.seedDemo) {
      await this.refreshSavedLessons();
    }
    let existing = this.videos.find((v) => v.youtube_video_id === videoId);
    let created = false;
    if (existing && !this.seedDemo) {
      existing = await this.openSavedLesson(existing.id);
    }
    if (!existing) {
      const official = isOfficialYoutubeId(videoId) && !videoId.startsWith("vid");
      if (!official && !videoId.startsWith("vid")) {
        throw new LibraryApiError(
          404,
          "NOT_FOUND",
          "Not a YouTube video URL. Paste a watch link like https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        );
      }
      let title = official ? `YouTube ${videoId}` : `Fixture import ${videoId} (synthetic)`;
      let channel = official ? "YouTube" : "LearnLens Fixtures";
      let transcriptAccess = false;
      let status: VideoRecord["status"] = "needs_transcript";
      let lesson: Record<string, unknown> | null = null;
      if (official && !this.seedDemo) {
        const lessonRes = await fetch("/api/gemini-lesson", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ videoId }),
        });
        const lessonBody = (await lessonRes.json().catch(() => null)) as {
          error?: string;
          title?: string;
          summary?: string;
          key_points?: string[];
          transcript?: string;
        } | null;
        if (!lessonRes.ok) {
          throw new LibraryApiError(
            lessonRes.status,
            "GEMINI_LESSON_FAILED",
            lessonBody?.error || "Gemini could not build a lesson from this video.",
          );
        }
        title = toLessonTitle(lessonBody?.title || "");
        if (!title) {
          try {
            const metaRes = await fetch(
              `/api/youtube-oembed?videoId=${encodeURIComponent(videoId)}`,
            );
            if (metaRes.ok) {
              const meta = (await metaRes.json()) as { title?: string; author_name?: string };
              title = toLessonTitle(meta.title || "");
              if (meta.author_name) channel = meta.author_name;
            }
          } catch {
            // Title stays as the video id when oEmbed is unreachable.
          }
        }
        title = title || `YouTube ${videoId}`;
        const summary = lessonBody?.summary || "";
        const keyPoints = lessonBody?.key_points || [];
        const transcript = lessonBody?.transcript || "";
        const sourceUrl = parsed.value.kind === "video" ? parsed.value.canonicalUrl : "";
        const saved = await this.persistLesson({
          videoId,
          title,
          channelTitle: channel === "YouTube" ? null : channel,
          summary,
          keyPoints,
          transcript,
          sourceUrl,
        });
        existing = saved.video;
        created = saved.created;
        this.videos = [
          existing,
          ...this.videos.filter((item) => item.id !== existing!.id),
        ];
        return {
          kind: "video",
          result: {
            video: existing,
            created,
            notices: [
              {
                code: "METADATA_ONLY",
                message: "Gemini built this lesson from the public YouTube video.",
              },
            ],
            companion_playlist_id:
              parsed.value.kind === "video" ? parsed.value.companionPlaylistId ?? null : null,
            transcript_from_url: false,
          },
        };
      } else if (official) {
        try {
          const metaRes = await fetch(`/api/youtube-oembed?videoId=${encodeURIComponent(videoId)}`);
          if (metaRes.ok) {
            const meta = (await metaRes.json()) as { title?: string; author_name?: string };
            if (meta.title) title = meta.title;
            if (meta.author_name) channel = meta.author_name;
          }
        } catch {
          // Title stays as the video id when oEmbed is unreachable.
        }
      }
      existing = {
        id: crypto.randomUUID(),
        workspace_id: FIXTURE_WORKSPACE_ID,
        youtube_video_id: videoId,
        title,
        status,
        channel_title: channel,
        duration_seconds: null,
        source_url: parsed.value.kind === "video" ? parsed.value.canonicalUrl : null,
        transcript_access: transcriptAccess,
        coverage: transcriptAccess ? "ready" : "metadata_only",
        fixture_data: !official,
        metadata_json: { fixture_data: !official, gemini_lesson: lesson },
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
            code: existing.fixture_data ? "FIXTURE_DATA" : "METADATA_ONLY",
            message: existing.transcript_access
              ? "Gemini built this lesson from the public YouTube video."
              : existing.fixture_data
                ? "Synthetic fixture metadata only — not a real YouTube transcript."
                : "Imported the public watch URL.",
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

  async getPlaylistCourseSummary(playlistId: string): Promise<PlaylistCourseSummary> {
    return this.request<PlaylistCourseSummary>(
      `/api/v1/playlists/${playlistId}/summary?ensure=true`,
    );
  }

  async synthesizePlaylist(playlistId: string): Promise<JobRecord> {
    const csrf = readCookie("ll_csrf");
    const headers: Record<string, string> = {
      "Idempotency-Key": crypto.randomUUID(),
    };
    if (csrf) headers["X-CSRF-Token"] = csrf;
    const accepted = await this.request<{
      job_id: string;
      status: string;
      stage: string;
      percent: number;
      playlist_id: string;
    }>(`/api/v1/playlists/${playlistId}/synthesize`, {
      method: "POST",
      headers,
    });
    try {
      return await this.getJob(accepted.job_id);
    } catch {
      const playlist = await this.getPlaylist(playlistId);
      return {
        id: accepted.job_id,
        workspace_id: playlist.workspace_id,
        video_id: null,
        job_type: "playlist_synthesis",
        status: accepted.status,
        stage: accepted.stage,
        attempt: 1,
        percent: accepted.percent,
      };
    }
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
  singleton = mode === "api" ? new HttpLibraryClient("") : new FixtureLibraryClient({ seedDemo: false });
  return singleton;
}

/** Test helper — reset singleton between Vitest cases. */
export function resetLibraryClient(client?: LibraryClient): void {
  singleton = client ?? null;
}
