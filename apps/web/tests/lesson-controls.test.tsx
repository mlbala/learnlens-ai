import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChapterTimeline } from "@/components/lesson/chapter-timeline";
import { LessonControls, REMOVE_CONFIRM, isGeminiLesson } from "@/components/library/lesson-controls";
import { LibraryToolbar } from "@/components/library/library-toolbar";

const VIDEO_ID = "11111111-1111-4111-8111-111111111111";

describe("isGeminiLesson", () => {
  it("needs transcript access, real data, and Gemini lesson metadata", () => {
    const lesson = { summary: "", key_points: [] };
    expect(
      isGeminiLesson({ transcript_access: true, fixture_data: false, metadata_json: { gemini_lesson: lesson } }),
    ).toBe(true);
    // A permitted transcript upload has access but is not a lesson.
    expect(isGeminiLesson({ transcript_access: true, fixture_data: false, metadata_json: {} })).toBe(false);
    expect(
      isGeminiLesson({ transcript_access: true, fixture_data: false, metadata_json: { gemini_lesson: undefined } }),
    ).toBe(false);
    expect(
      isGeminiLesson({ transcript_access: true, fixture_data: true, metadata_json: { gemini_lesson: lesson } }),
    ).toBe(false);
    expect(
      isGeminiLesson({ transcript_access: false, fixture_data: false, metadata_json: { gemini_lesson: lesson } }),
    ).toBe(false);
  });
});

describe("LessonControls", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("asks before Remove and does nothing when cancelled", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const afterRemove = vi.fn();
    render(<LessonControls videoId={VIDEO_ID} title="Tides" afterRemove={afterRemove} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove Tides" }));
    expect(confirm).toHaveBeenCalledWith(REMOVE_CONFIRM);
    expect(REMOVE_CONFIRM).toMatch(/lesson, its notes, and its Ask AI thread/);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(afterRemove).not.toHaveBeenCalled();
  });

  it("sends DELETE after confirmation and reports removal", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChanged = vi.fn();
    const afterRemove = vi.fn();
    render(
      <LessonControls videoId={VIDEO_ID} title="Tides" onChanged={onChanged} afterRemove={afterRemove} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove Tides" }));
    await waitFor(() => expect(afterRemove).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/learning-history/${VIDEO_ID}`,
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(onChanged).toHaveBeenCalled();
  });

  it("shows an error and stays put when Remove fails", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 503 }));
    const afterRemove = vi.fn();
    render(<LessonControls videoId={VIDEO_ID} title="Tides" afterRemove={afterRemove} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove Tides" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not remove this lesson.");
    expect(afterRemove).not.toHaveBeenCalled();
  });

  it("PUTs { pinned: true } and flips to Unpin", async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ video_id: VIDEO_ID, pinned: true }));
    const onPinnedChange = vi.fn();
    render(<LessonControls videoId={VIDEO_ID} title="Tides" onPinnedChange={onPinnedChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Pin Tides" }));
    expect(await screen.findByRole("button", { name: "Unpin Tides" })).toBeInTheDocument();
    expect(screen.getByText("Pinned")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/learning-history/${VIDEO_ID}/pin`);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({ pinned: true });
    expect(onPinnedChange).toHaveBeenCalledWith(true);
  });

  it("does not treat a Pin 404 as a removal", async () => {
    fetchMock.mockResolvedValueOnce(
      Response.json({ error: { code: "LESSON_NOT_IN_WORKSPACE" } }, { status: 404 }),
    );
    const afterRemove = vi.fn();
    render(<LessonControls videoId={VIDEO_ID} title="Tides" afterRemove={afterRemove} />);
    fireEvent.click(screen.getByRole("button", { name: "Pin Tides" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no longer in this workspace/);
    expect(afterRemove).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Pin Tides" })).toBeInTheDocument();
  });
});

describe("Chapters without verified times", () => {
  it("shows the title and disables seek", () => {
    const onSeek = vi.fn();
    render(
      <ChapterTimeline
        chapters={[
          { id: "c1", video_id: "v", workspace_id: "w", source_revision: 1, title: "Intro", start_ms: null },
        ]}
        onSeek={onSeek}
      />,
    );
    expect(screen.getByText("Intro")).toBeInTheDocument();
    const jump = screen.getByRole("button", { name: /has no verified time/ });
    expect(jump).toBeDisabled();
    fireEvent.click(jump);
    expect(onSeek).not.toHaveBeenCalled();
  });
});

describe("LibraryToolbar status filter", () => {
  function renderToolbar(hideNeedsTranscript: boolean) {
    render(
      <LibraryToolbar
        view="grid"
        onViewChange={() => undefined}
        status="all"
        onStatusChange={() => undefined}
        query=""
        onQueryChange={() => undefined}
        hideNeedsTranscript={hideNeedsTranscript}
      />,
    );
  }

  it("hides Needs transcript on the Videos page", () => {
    renderToolbar(true);
    expect(screen.queryByRole("option", { name: "Needs transcript" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Ready" })).toBeInTheDocument();
  });

  it("keeps Needs transcript elsewhere", () => {
    renderToolbar(false);
    expect(screen.getByRole("option", { name: "Needs transcript" })).toBeInTheDocument();
  });
});
