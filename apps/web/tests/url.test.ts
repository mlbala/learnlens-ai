import { describe, expect, it } from "vitest";

import { parseSourceUrl } from "@/lib/library/url";

describe("parseSourceUrl", () => {
  it("detects fixture video and playlist URLs", () => {
    const video = parseSourceUrl("https://www.youtube.com/watch?v=vidPublic01");
    expect(video.ok).toBe(true);
    if (video.ok) {
      expect(video.value.kind).toBe("video");
      if (video.value.kind === "video") {
        expect(video.value.videoId).toBe("vidPublic01");
      }
    }

    const playlist = parseSourceUrl(
      "https://www.youtube.com/playlist?list=PLfixtureCourse01",
    );
    expect(playlist.ok).toBe(true);
    if (playlist.ok) {
      expect(playlist.value.kind).toBe("playlist");
    }
  });

  it("rejects credentialed and evil hosts", () => {
    expect(
      parseSourceUrl("https://user:pass@www.youtube.com/watch?v=vidPublic01").ok,
    ).toBe(false);
    expect(
      parseSourceUrl("https://youtube.com.evil.example/watch?v=vidPublic01").ok,
    ).toBe(false);
  });

  it("surfaces companion playlist on watch URLs", () => {
    const parsed = parseSourceUrl(
      "https://www.youtube.com/watch?v=vidPublic01&list=PLfixtureCourse01",
    );
    expect(parsed.ok).toBe(true);
    if (parsed.ok && parsed.value.kind === "video") {
      expect(parsed.value.companionPlaylistId).toBe("PLfixtureCourse01");
    }
  });
});
