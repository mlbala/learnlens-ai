/**
 * Offline demo library — synthetic fixture data only.
 * Never presented as real YouTube transcripts or captions.
 */

import { normalizeCoverage } from "@/lib/library/coverage";
import type {
  DashboardStats,
  JobRecord,
  PlaylistRecord,
  PlaylistSummary,
  VideoRecord,
} from "@/lib/library/types";

export const FIXTURE_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001";
export const FIXTURE_MODE_LABEL = "Demo fixture mode";
export const FIXTURE_MODE_DESCRIPTION =
  "Showing synthetic LearnLens fixtures. Not real YouTube captions or transcripts. No YouTube Data API key required.";

const WS = FIXTURE_WORKSPACE_ID;

function video(
  partial: Omit<VideoRecord, "workspace_id" | "transcript_access" | "fixture_data"> & {
    transcript_access?: boolean;
  },
): VideoRecord {
  const ready = partial.status === "ready";
  return {
    workspace_id: WS,
    transcript_access: partial.transcript_access ?? ready,
    fixture_data: true,
    coverage: ready ? "ready" : partial.coverage ?? "metadata_only",
    ...partial,
  };
}

/** Seed videos — titles marked synthetic; some ready only after fixture “upload”. */
export const FIXTURE_VIDEOS: VideoRecord[] = [
  video({
    id: "11111111-1111-4111-8111-111111111101",
    youtube_video_id: "vidPublic01",
    title: "Fixture lecture 1: Active listening (synthetic)",
    status: "ready",
    channel_title: "LearnLens Fixtures",
    duration_seconds: 600,
    source_url: "https://www.youtube.com/watch?v=vidPublic01",
    coverage: "ready",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111102",
    youtube_video_id: "vidPublic02",
    title: "Fixture lecture 2: Clarifying questions (synthetic)",
    status: "ready",
    channel_title: "LearnLens Fixtures",
    duration_seconds: 720,
    source_url: "https://www.youtube.com/watch?v=vidPublic02",
    coverage: "ready",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111103",
    youtube_video_id: "vidPublic03",
    title: "Fixture lecture 3: Feedback loops (synthetic)",
    status: "needs_transcript",
    channel_title: "LearnLens Fixtures",
    duration_seconds: 540,
    source_url: "https://www.youtube.com/watch?v=vidPublic03",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111104",
    youtube_video_id: "vidPublic04",
    title: "Fixture lecture 4: Conflict basics (synthetic)",
    status: "ready",
    channel_title: "LearnLens Fixtures",
    duration_seconds: 480,
    source_url: "https://www.youtube.com/watch?v=vidPublic04",
    coverage: "ready",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111105",
    youtube_video_id: "vidPublic05",
    title: "Fixture lecture 5: Closing conversations (synthetic)",
    status: "failed_retryable",
    channel_title: "LearnLens Fixtures",
    duration_seconds: 510,
    source_url: "https://www.youtube.com/watch?v=vidPublic05",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111191",
    youtube_video_id: "vidPrivate9",
    title: "Fixture private item (synthetic)",
    status: "unavailable",
    channel_title: null,
    duration_seconds: null,
    source_url: "https://www.youtube.com/watch?v=vidPrivate9",
    coverage: "unavailable",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111192",
    youtube_video_id: "vidDeleted1",
    title: "Fixture deleted item (synthetic)",
    status: "unavailable",
    channel_title: null,
    duration_seconds: null,
    source_url: "https://www.youtube.com/watch?v=vidDeleted1",
    coverage: "unavailable",
  }),
  video({
    id: "11111111-1111-4111-8111-111111111193",
    youtube_video_id: "vidUnavail1",
    title: "Fixture unavailable item (synthetic)",
    status: "unavailable",
    channel_title: null,
    duration_seconds: null,
    source_url: "https://www.youtube.com/watch?v=vidUnavail1",
    coverage: "unavailable",
  }),
];

const PLAYLIST_ID = "22222222-2222-4222-8222-222222222201";

/** Coverage matches docs §7 spirit: partial with unavailable — never 100%. */
export const FIXTURE_PLAYLIST_COVERAGE = normalizeCoverage({
  total: 7,
  ready: 3,
  needs_transcript: 1,
  unavailable: 2,
  failed: 1,
});

export const FIXTURE_PLAYLIST: PlaylistRecord = {
  id: PLAYLIST_ID,
  workspace_id: WS,
  youtube_playlist_id: "PLfixtureCourse01",
  title: "Fixture communication course (synthetic)",
  status: "partial",
  total_items: 7,
  channel_title: "LearnLens Fixtures",
  transcript_from_url: false,
  fixture_data: true,
  coverage: FIXTURE_PLAYLIST_COVERAGE,
  items: [
    {
      id: "33333333-3333-4333-8333-333333333301",
      playlist_position: 0,
      youtube_video_id: "vidPublic01",
      video_id: "11111111-1111-4111-8111-111111111101",
      state: "ready",
      title: "Fixture lecture 1: Active listening (synthetic)",
      duration_seconds: 600,
      channel_title: "LearnLens Fixtures",
    },
    {
      id: "33333333-3333-4333-8333-333333333302",
      playlist_position: 1,
      youtube_video_id: "vidPublic02",
      video_id: "11111111-1111-4111-8111-111111111102",
      state: "ready",
      title: "Fixture lecture 2: Clarifying questions (synthetic)",
      duration_seconds: 720,
      channel_title: "LearnLens Fixtures",
    },
    {
      id: "33333333-3333-4333-8333-333333333303",
      playlist_position: 2,
      youtube_video_id: "vidPrivate9",
      video_id: "11111111-1111-4111-8111-111111111191",
      state: "unavailable",
      title: "Fixture private item (synthetic)",
    },
    {
      id: "33333333-3333-4333-8333-333333333304",
      playlist_position: 3,
      youtube_video_id: "vidPublic03",
      video_id: "11111111-1111-4111-8111-111111111103",
      state: "needs_transcript",
      title: "Fixture lecture 3: Feedback loops (synthetic)",
      duration_seconds: 540,
      channel_title: "LearnLens Fixtures",
    },
    {
      id: "33333333-3333-4333-8333-333333333305",
      playlist_position: 4,
      youtube_video_id: "vidDeleted1",
      video_id: "11111111-1111-4111-8111-111111111192",
      state: "unavailable",
      title: "Fixture deleted item (synthetic)",
    },
    {
      id: "33333333-3333-4333-8333-333333333306",
      playlist_position: 5,
      youtube_video_id: "vidPublic04",
      video_id: "11111111-1111-4111-8111-111111111104",
      state: "ready",
      title: "Fixture lecture 4: Conflict basics (synthetic)",
      duration_seconds: 480,
      channel_title: "LearnLens Fixtures",
    },
    {
      id: "33333333-3333-4333-8333-333333333307",
      playlist_position: 6,
      youtube_video_id: "vidPublic05",
      video_id: "11111111-1111-4111-8111-111111111105",
      state: "failed",
      title: "Fixture lecture 5: Closing conversations (synthetic)",
      duration_seconds: 510,
      channel_title: "LearnLens Fixtures",
    },
  ],
};

export function fixturePlaylistSummary(): PlaylistSummary {
  return {
    id: FIXTURE_PLAYLIST.id,
    workspace_id: FIXTURE_PLAYLIST.workspace_id,
    youtube_playlist_id: FIXTURE_PLAYLIST.youtube_playlist_id,
    title: FIXTURE_PLAYLIST.title,
    status: FIXTURE_PLAYLIST.status,
    total_items: FIXTURE_PLAYLIST.total_items,
    channel_title: FIXTURE_PLAYLIST.channel_title,
    coverage: FIXTURE_PLAYLIST.coverage,
    fixture_data: true,
  };
}

export function fixtureDashboardStats(videos: VideoRecord[]): DashboardStats {
  return {
    videos_ready: videos.filter((v) => v.status === "ready").length,
    playlists: 1,
    processing: videos.filter((v) =>
      ["queued", "processing", "validating", "segmenting"].includes(v.status),
    ).length,
    pending_transcripts: videos.filter((v) =>
      ["needs_transcript", "metadata_only"].includes(v.status),
    ).length,
    jobs_needing_attention: videos.filter((v) =>
      ["failed_retryable", "failed", "failed_terminal"].includes(v.status),
    ).length,
    mode: "fixture",
  };
}

export function cloneFixtureJob(
  videoId: string,
  overrides: Partial<JobRecord> = {},
): JobRecord {
  return {
    id: overrides.id ?? crypto.randomUUID(),
    workspace_id: WS,
    video_id: videoId,
    job_type: "transcript_ingest",
    status: "queued",
    stage: "pending",
    attempt: 1,
    percent: 0,
    ...overrides,
  };
}
