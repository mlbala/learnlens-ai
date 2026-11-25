import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardHome } from "@/components/library/dashboard-home";

vi.mock("@/lib/library/query", () => ({
  useDashboardStats: () => ({
    isLoading: false,
    isError: false,
    data: {
      videos_ready: 3,
      playlists: 1,
      processing: 0,
      pending_transcripts: 2,
      jobs_needing_attention: 1,
      mode: "fixture",
    },
  }),
  useVideosInfinite: () => ({ data: { pages: [{ items: [] }] } }),
}));
vi.mock("@/components/library/import-source-dialog", () => ({
  ImportSourceDialog: () => <button type="button">Paste a link</button>,
}));
vi.mock("@/components/HealthStatus", () => ({ HealthStatus: () => null }));

describe("Home", () => {
  it("keeps Lessons saved and Playlists and drops transcript-queue copy", () => {
    render(<DashboardHome />);
    expect(screen.getByText("Lessons saved")).toBeInTheDocument();
    expect(screen.getByText("Playlists")).toBeInTheDocument();
    expect(screen.queryByText(/Pending transcripts/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Jobs needing attention/)).not.toBeInTheDocument();
  });
});
