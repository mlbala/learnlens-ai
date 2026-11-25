import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VideoDetail } from "@/components/library/video-detail";
import type { VideoRecord } from "@/lib/library/types";

let current: VideoRecord;

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/library/query", () => ({
  libraryKeys: { all: ["library"], video: (id: string) => ["library", "video", id], dashboard: () => ["library", "dashboard"] },
  useVideo: () => ({ isLoading: false, isError: false, data: current, refetch: vi.fn() }),
}));
vi.mock("@/components/lesson/lesson-reader", () => ({ LessonReader: () => <div>Lesson reader</div> }));
vi.mock("@/components/lesson/youtube-player", () => ({ YoutubePlayer: () => <div>Player</div> }));
vi.mock("@/components/library/transcript-import-dialog", () => ({
  TranscriptImportDialog: () => <button type="button">Upload transcript</button>,
}));

const base: VideoRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  workspace_id: "00000000-0000-4000-8000-000000000001",
  youtube_video_id: "dQw4w9WgXcQ",
  title: "Tides",
  status: "ready",
  transcript_access: true,
  fixture_data: false,
};

function renderDetail(video: VideoRecord) {
  current = video;
  render(
    <QueryClientProvider client={new QueryClient()}>
      <VideoDetail videoId={video.id} />
    </QueryClientProvider>,
  );
}

describe("Lesson page", () => {
  it("offers Pin and Remove and no transcript upload on a Gemini lesson", () => {
    renderDetail({ ...base, metadata_json: { gemini_lesson: { summary: "", key_points: [] } } });
    expect(screen.getByRole("button", { name: "Pin Tides" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove Tides" })).toBeInTheDocument();
    expect(screen.queryByText("Upload transcript")).not.toBeInTheDocument();
    expect(screen.queryByText(/Owner-authorized caption download/)).not.toBeInTheDocument();
  });

  it("keeps the upload empty state for a video with no transcript", () => {
    renderDetail({ ...base, status: "needs_transcript", transcript_access: false });
    expect(screen.getAllByText("Upload transcript").length).toBeGreaterThan(0);
    expect(screen.getByText("No transcript attached")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Remove/ })).not.toBeInTheDocument();
  });
});
