import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LessonReader } from "@/components/lesson/lesson-reader";
import type { LessonBundle, LessonChapter } from "@/lib/lesson/types";
import type { VideoRecord } from "@/lib/library/types";

let bundle: LessonBundle;

vi.mock("@/lib/lesson/query", () => ({
  useLessonBundle: () => ({
    isLoading: false,
    isError: false,
    data: bundle,
    refetch: vi.fn(),
  }),
}));
vi.mock("@/components/lesson/chat-panel", () => ({ ChatPanel: () => <div>Ask AI panel</div> }));
vi.mock("@/components/lesson/youtube-player", () => ({ YoutubePlayer: () => <div>Player</div> }));

const video: VideoRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  workspace_id: "00000000-0000-4000-8000-000000000001",
  youtube_video_id: "dQw4w9WgXcQ",
  title: "Photosynthesis",
  status: "ready",
  transcript_access: true,
  fixture_data: false,
};

function bundleWith(chapters: LessonChapter[]): LessonBundle {
  return {
    chapters,
    summaries: [],
    snippets: [],
    starter_questions: [],
    fixture_data: false,
  };
}

describe("LessonReader chapters", () => {
  it("omits the Chapters tab when the lesson has no chapters", () => {
    bundle = bundleWith([]);
    render(<LessonReader video={video} />);
    expect(screen.getByRole("tab", { name: /Study notes/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Transcript/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Chapters/ })).not.toBeInTheDocument();
  });

  it("shows the Chapters tab when a chapter exists", () => {
    bundle = bundleWith([
      {
        id: "c1",
        video_id: video.id,
        workspace_id: video.workspace_id,
        source_revision: 1,
        title: "Light reactions",
        start_ms: null,
      },
    ]);
    render(<LessonReader video={video} />);
    expect(screen.getByRole("tab", { name: /Chapters/ })).toBeInTheDocument();
  });
});
