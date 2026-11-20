import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EvidenceCitation } from "@/components/lesson/evidence-citation";
import type { Citation } from "@/lib/lesson/types";

const timed: Citation = {
  citation_id: "c_01",
  video_id: "vid",
  video_title: "Fixture lecture",
  segment_id: "seg",
  snippet: "Fixture timed snippet (synthetic)",
  start_ms: 95_000,
  end_ms: 118_000,
  youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=95s",
  timing_verified: true,
};

const untimed: Citation = {
  citation_id: "c_03",
  video_id: "vid",
  video_title: "Fixture lecture",
  segment_id: "seg",
  snippet: "Fixture untimed snippet (synthetic)",
  start_ms: null,
  end_ms: null,
  youtube_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  timing_verified: false,
};

describe("EvidenceCitation", () => {
  it("jumps in player for verified timing", async () => {
    const user = userEvent.setup();
    const onSeek = vi.fn();
    render(<EvidenceCitation citation={timed} youtubeVideoId="dQw4w9WgXcQ" onSeek={onSeek} />);
    expect(screen.getByTestId("citation-c_01")).toHaveAttribute("data-timing-verified", "true");
    await user.click(screen.getByRole("button", { name: /jump in player/i }));
    expect(onSeek).toHaveBeenCalledWith(95);
    expect(screen.getByRole("link", { name: /open source at/i })).toHaveAttribute(
      "href",
      expect.stringContaining("t=95s"),
    );
  });

  it("does not claim a precise moment for non-timed citations", () => {
    render(<EvidenceCitation citation={untimed} youtubeVideoId="dQw4w9WgXcQ" />);
    expect(screen.getByText(/source available without exact time/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /jump in player/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open source without exact time/i })).toHaveAttribute(
      "href",
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    );
  });
});
