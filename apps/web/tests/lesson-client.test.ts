import { afterEach, describe, expect, it } from "vitest";

import { FixtureLessonClient, resetLessonClient } from "@/lib/lesson/client";
import {
  FIXTURE_LESSON_VIDEO_ID,
  resetFixtureChatStore,
} from "@/lib/lesson/fixtures";
import { LessonApiError } from "@/lib/lesson/types";
import { FixtureLibraryClient, resetLibraryClient } from "@/lib/library/client";

afterEach(() => {
  resetFixtureChatStore();
  resetLessonClient();
  resetLibraryClient();
});

describe("FixtureLessonClient", () => {
  it("returns fixture chapters, notes, and snippets for ready lesson video", async () => {
    resetLibraryClient(new FixtureLibraryClient());
    const client = new FixtureLessonClient();
    const bundle = await client.getLessonBundle(FIXTURE_LESSON_VIDEO_ID);
    expect(bundle.fixture_data).toBe(true);
    expect(bundle.chapters.length).toBeGreaterThan(0);
    expect(bundle.summaries.some((s) => s.summary_kind === "short")).toBe(true);
    expect(bundle.snippets.some((s) => s.start_ms == null)).toBe(true);
    expect(bundle.starter_questions.length).toBeGreaterThan(0);
  });

  it("persists chat threads and returns timed + recoverable errors", async () => {
    resetLibraryClient(new FixtureLibraryClient());
    const client = new FixtureLessonClient();
    const thread = await client.ensureThread(FIXTURE_LESSON_VIDEO_ID);
    expect(thread.scope_id).toBe(FIXTURE_LESSON_VIDEO_ID);

    const ok = await client.postMessage({
      threadId: thread.id,
      question: "What does active listening require first?",
      explanationMode: "simple",
    });
    expect(ok.assistant_message.citations[0]?.timing_verified).toBe(true);
    expect(ok.assistant_message.analogies[0]?.origin).toBe("ai_generated_illustration");

    const untimed = await client.postMessage({
      threadId: thread.id,
      question: "Show an untimed source without exact time",
      explanationMode: "standard",
    });
    expect(untimed.assistant_message.citations[0]?.timing_verified).toBe(false);
    expect(untimed.assistant_message.citations[0]?.start_ms).toBeNull();

    const listed = await client.listMessages(thread.id);
    expect(listed.length).toBe(4);

    await expect(
      client.postMessage({
        threadId: thread.id,
        question: "FORCE_CHAT_ERROR please",
        explanationMode: "standard",
      }),
    ).rejects.toBeInstanceOf(LessonApiError);
  });

  it("hides lesson content when transcript access is missing", async () => {
    resetLibraryClient(new FixtureLibraryClient());
    const client = new FixtureLessonClient();
    const bundle = await client.getLessonBundle("11111111-1111-4111-8111-111111111103");
    expect(bundle.chapters).toEqual([]);
    expect(bundle.summaries).toEqual([]);
    expect(bundle.snippets).toEqual([]);
  });
});
