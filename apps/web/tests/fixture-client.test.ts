import { afterEach, describe, expect, it } from "vitest";

import { FixtureLibraryClient, resetLibraryClient } from "@/lib/library/client";
import { LibraryApiError } from "@/lib/library/types";

afterEach(() => {
  resetLibraryClient();
});

describe("FixtureLibraryClient", () => {
  it("lists fixture videos with pagination", async () => {
    const client = new FixtureLibraryClient();
    const page1 = await client.listVideos({ limit: 3 });
    expect(page1.mode).toBe("fixture");
    expect(page1.items).toHaveLength(3);
    expect(page1.next_cursor).toBe("3");
    expect(page1.items.every((v) => v.fixture_data)).toBe(true);

    const page2 = await client.listVideos({ cursor: page1.next_cursor, limit: 3 });
    expect(page2.items.length).toBeGreaterThan(0);
  });

  it("returns honest playlist coverage counts", async () => {
    const client = new FixtureLibraryClient();
    const playlist = await client.getPlaylist("22222222-2222-4222-8222-222222222201");
    expect(playlist.transcript_from_url).toBe(false);
    expect(playlist.coverage.ready).toBe(3);
    expect(playlist.coverage.total).toBe(7);
    expect(playlist.coverage.unavailable).toBe(2);
    expect(playlist.coverage.failed).toBe(1);
    expect(playlist.coverage.needs_transcript).toBe(1);
    expect(playlist.coverage.ready + playlist.coverage.missing).toBe(7);
  });

  it("imports fixture video without granting transcript access", async () => {
    const client = new FixtureLibraryClient();
    const result = await client.importSource(
      "https://www.youtube.com/watch?v=vidPublic01",
    );
    expect(result.kind).toBe("video");
    if (result.kind === "video") {
      expect(result.result.transcript_from_url).toBe(false);
      expect(result.result.video.transcript_access).toBe(
        result.result.video.status === "ready",
      );
      expect(result.result.notices.some((n) => n.code === "FIXTURE_DATA")).toBe(true);
    }
  });

  it("imports a real YouTube watch URL without fixture rejection", async () => {
    const client = new FixtureLibraryClient();
    const result = await client.importSource(
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    );
    expect(result.kind).toBe("video");
    if (result.kind === "video") {
      expect(result.result.video.youtube_video_id).toBe("dQw4w9WgXcQ");
      expect(result.result.video.fixture_data).toBe(false);
      expect(result.result.video.transcript_access).toBe(false);
      expect(result.result.transcript_from_url).toBe(false);
    }
  });

  it("rejects transcript upload without attestation", async () => {
    const client = new FixtureLibraryClient();
    await expect(
      client.uploadTranscript({
        videoId: "11111111-1111-4111-8111-111111111103",
        rightsAttested: false,
        sourceKind: "paste",
        pasteText: "fixture paste only",
      }),
    ).rejects.toBeInstanceOf(LibraryApiError);
  });

  it("accepts attested paste and progresses job without inventing YouTube captions", async () => {
    const client = new FixtureLibraryClient();
    const accepted = await client.uploadTranscript({
      videoId: "11111111-1111-4111-8111-111111111103",
      rightsAttested: true,
      sourceKind: "paste",
      pasteText: "Synthetic fixture transcript text — not YouTube captions.",
    });
    expect(accepted.job_id).toBeTruthy();
    expect(accepted.timecode_quality).toBe("none");

    await new Promise((r) => setTimeout(r, 20));
    const job = await client.getJob(accepted.job_id);
    expect(["running", "succeeded"]).toContain(job.status);

    await new Promise((r) => setTimeout(r, 20));
    const video = await client.getVideo("11111111-1111-4111-8111-111111111103");
    expect(video.status).toBe("ready");
    expect(video.transcript_access).toBe(true);
    expect(video.metadata_json?.fixture_transcript).toBe(true);
  });
});
