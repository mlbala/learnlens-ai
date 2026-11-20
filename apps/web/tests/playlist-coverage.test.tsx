import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlaylistCoverageBar } from "@/components/library/playlist-coverage";
import { normalizeCoverage } from "@/lib/library/coverage";

describe("PlaylistCoverageBar", () => {
  it("shows ready/total and limitation counts with partial badge", () => {
    const coverage = normalizeCoverage({
      total: 15,
      ready: 10,
      needs_transcript: 2,
      unavailable: 1,
      failed: 2,
    });
    render(<PlaylistCoverageBar coverage={coverage} />);
    expect(screen.getByText("10 of 15 ready")).toBeInTheDocument();
    expect(screen.getByLabelText("Partial coverage")).toBeInTheDocument();
    expect(screen.getByText(/Needs transcript 2/)).toBeInTheDocument();
    expect(screen.getByText(/Unavailable 1/)).toBeInTheDocument();
    expect(screen.getByText(/Failed 2/)).toBeInTheDocument();
    expect(screen.getByText(/Missing 5/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow");
    const now = Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"));
    expect(now).toBeLessThan(100);
  });
});
