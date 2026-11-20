import { describe, expect, it } from "vitest";

import {
  citationLabel,
  citationOpenUrl,
  citationSeekSeconds,
  citationTimingHint,
  isOfficialYoutubeId,
  youtubeEmbedSrc,
} from "@/lib/lesson/citations";
import type { Citation } from "@/lib/lesson/types";

const timed: Citation = {
  citation_id: "c_01",
  video_id: "vid",
  video_title: "Fixture lecture",
  segment_id: "seg",
  snippet: "synthetic snippet",
  start_ms: 123_000,
  end_ms: 142_000,
  youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123s",
  timing_verified: true,
};

const untimed: Citation = {
  citation_id: "c_02",
  video_id: "vid",
  video_title: "Fixture lecture",
  segment_id: "seg",
  snippet: "untimed synthetic snippet",
  start_ms: null,
  end_ms: null,
  youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=999s",
  timing_verified: false,
};

describe("citation helpers", () => {
  it("seeks only when timing is verified", () => {
    expect(citationSeekSeconds(timed)).toBe(123);
    expect(citationSeekSeconds(untimed)).toBeNull();
    expect(citationTimingHint(untimed)).toBe("Source available without exact time");
    expect(citationLabel(timed)).toContain("2:03");
  });

  it("strips accidental t= for unverified citations", () => {
    const url = citationOpenUrl(untimed);
    expect(url).toBeTruthy();
    expect(url!).not.toContain("t=");
    expect(citationOpenUrl(timed)).toContain("t=123s");
  });

  it("never invents timed links without verified start_ms", () => {
    const bare: Citation = { ...untimed, youtube_url: null };
    expect(citationOpenUrl(bare, "dQw4w9WgXcQ")).toBe(
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    );
    // Fixture ids may still open a watch URL without t= — never add a fabricated time.
    expect(citationOpenUrl(bare, "vidPublic01")).toBe(
      "https://www.youtube.com/watch?v=vidPublic01",
    );
  });

  it("builds official embed src with optional start", () => {
    expect(isOfficialYoutubeId("dQw4w9WgXcQ")).toBe(true);
    expect(isOfficialYoutubeId("short")).toBe(false);
    const src = youtubeEmbedSrc("dQw4w9WgXcQ", { startSeconds: 45 });
    expect(src).toContain("embed/dQw4w9WgXcQ");
    expect(src).toContain("start=45");
  });
});
