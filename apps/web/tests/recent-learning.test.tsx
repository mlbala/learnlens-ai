import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecentLearningList } from "@/components/recent/recent-learning";
import type { VideoRecord } from "@/lib/library/types";

const lesson: VideoRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  workspace_id: "00000000-0000-4000-8000-000000000001",
  youtube_video_id: "dQw4w9WgXcQ",
  title: "Photosynthesis",
  status: "ready",
  channel_title: "Biology Channel",
  transcript_access: true,
  coverage: "ready",
  fixture_data: false,
};

describe("Recent Learning", () => {
  it("renders saved lessons instead of Coming Soon", () => {
    render(<RecentLearningList lessons={[lesson]} />);
    const link = screen.getByRole("link", { name: "Open Photosynthesis" });
    expect(link).toHaveAttribute("href", `/videos/${lesson.id}`);
    expect(screen.getByText("Biology Channel")).toBeInTheDocument();
    expect(screen.queryByText("Not available yet")).not.toBeInTheDocument();
    expect(screen.queryByText(/later phase/i)).not.toBeInTheDocument();
  });

  it("tells the user to paste a public YouTube link when history is empty", () => {
    render(<RecentLearningList lessons={[]} />);
    expect(screen.getByText("No recent lessons")).toBeInTheDocument();
    expect(screen.getByText(/Paste a public YouTube link/)).toBeInTheDocument();
  });
});
