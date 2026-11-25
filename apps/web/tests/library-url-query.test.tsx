import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LibraryBrowser } from "@/components/library/library-browser";

let search = "q=Photosynthesis";
const videoFilters: Array<{ q?: string }> = [];

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/lib/library/query", () => ({
  libraryKeys: { all: ["library"], dashboard: () => ["library", "dashboard"] },
  useVideosInfinite: (filters: { q?: string }) => {
    videoFilters.push(filters);
    return { data: { pages: [{ items: [] }] }, isLoading: false, isError: false };
  },
  usePlaylistsInfinite: () => ({ data: { pages: [{ items: [] }] }, isLoading: false, isError: false }),
}));
vi.mock("@/components/library/import-source-dialog", () => ({ ImportSourceDialog: () => null }));

function renderVideos() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LibraryBrowser initialKind="videos" title="Videos" />
    </QueryClientProvider>,
  );
}

describe("Videos page reads q from the URL", () => {
  it("passes ?q= to the title filter and fills the search box", () => {
    videoFilters.length = 0;
    search = "q=Photosynthesis";
    renderVideos();
    expect(videoFilters[0]?.q).toBe("Photosynthesis");
    expect(screen.getByLabelText("Search titles")).toHaveValue("Photosynthesis");
  });

  it("has no title filter when q is absent", () => {
    videoFilters.length = 0;
    search = "";
    renderVideos();
    expect(videoFilters[0]?.q).toBeUndefined();
  });
});
