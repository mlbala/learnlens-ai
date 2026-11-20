import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceCitation } from "@/components/lesson/evidence-citation";
import { TranscriptPanel } from "@/components/lesson/transcript-panel";
import type { Citation } from "@/lib/lesson/types";

describe("XSS escape — React text nodes", () => {
  it("renders transcript script tags as text, not executable HTML", () => {
    const payload = "<script>alert(1)</script> listening skills";
    render(
      <TranscriptPanel
        snippets={[
          {
            id: "s1",
            ordinal: 1,
            text: payload,
            start_ms: 1000,
            end_ms: 2000,
            content_hash: "fixture",
            fixture_data: true,
          },
        ]}
      />,
    );
    expect(screen.getByText(payload)).toBeTruthy();
    expect(document.querySelector("script")).toBeNull();
  });

  it("renders citation snippets with markup as escaped text", () => {
    const citation: Citation = {
      citation_id: "c_xss",
      video_id: "vid",
      video_title: "Fixture",
      segment_id: "seg",
      snippet: "<img src=x onerror=alert(1)> forged claim",
      start_ms: null,
      end_ms: null,
      youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      timing_verified: false,
    };
    render(<EvidenceCitation citation={citation} youtubeVideoId="dQw4w9WgXcQ" />);
    expect(screen.getByText(/forged claim/)).toBeTruthy();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });
});
