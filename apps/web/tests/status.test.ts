import { describe, expect, it } from "vitest";

import {
  isProcessingStatus,
  playlistCoverageLabel,
  presentStatus,
} from "@/lib/status";

describe("presentStatus", () => {
  it("maps needs_transcript to amber action copy", () => {
    expect(presentStatus("needs_transcript")).toEqual({
      label: "Transcript needed",
      tone: "warning",
      actionHint: "Add transcript",
    });
  });

  it("maps ready to success without marketing claims", () => {
    expect(presentStatus("ready")).toEqual({
      label: "Ready to study",
      tone: "success",
    });
  });

  it("maps unknown status safely", () => {
    expect(presentStatus("not_a_real_status")).toEqual({
      label: "Unknown status",
      tone: "neutral",
    });
  });

  it("treats pipeline stages as processing", () => {
    expect(isProcessingStatus("summarizing")).toBe(true);
    expect(isProcessingStatus("ready")).toBe(false);
    expect(presentStatus("queued").label).toBe("Processing");
  });
});

describe("playlistCoverageLabel", () => {
  it("states honest partial coverage", () => {
    expect(playlistCoverageLabel(9, 12)).toBe("Summary covers 9 of 12 videos");
  });

  it("states complete coverage when ready equals total", () => {
    expect(playlistCoverageLabel(12, 12)).toBe("Summary covers 12 of 12 videos");
  });

  it("rejects invalid counts without inventing content", () => {
    expect(playlistCoverageLabel(-1, 5)).toBe("Coverage unavailable");
    expect(playlistCoverageLabel(0, 0)).toBe("No videos in playlist");
  });
});
