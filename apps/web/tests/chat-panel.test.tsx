import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ChatPanel, OFF_SUBJECT_NOTE } from "@/components/lesson/chat-panel";
import { asTutorAnswer } from "@/lib/lesson/answer";
import { resetLessonClient, type LessonClient } from "@/lib/lesson/client";
import type { ChatMessage, ChatThread, LessonBundle, PostChatResult } from "@/lib/lesson/types";

const thread: ChatThread = {
  id: "thread-1",
  workspace_id: "ws",
  scope_kind: "video",
  scope_id: "video-1",
  title: "Lesson chat",
  created_by: "user",
  created_at: "2026-11-22T00:00:00Z",
};

const messages: ChatMessage[] = [
  {
    id: "u1",
    thread_id: thread.id,
    workspace_id: "ws",
    role: "user",
    content: "What is an agent?",
    unsupported: false,
    claims: [],
    analogies: [],
    citations: [],
    created_at: "2026-11-22T00:00:01Z",
    external_search_enabled: true,
  },
  {
    id: "a1",
    thread_id: thread.id,
    workspace_id: "ws",
    role: "assistant",
    content: "### Raw heading\nThis plain fallback must not replace the cards.",
    unsupported: false,
    claims: [],
    analogies: [],
    citations: [],
    created_at: "2026-11-22T00:00:02Z",
    content_json: {
      v: 1,
      lesson: [{ heading: "What it is", body: "Stored lesson card." }],
      external: [],
      sources: [],
      web_search: {
        queries: ["agent memory official docs"],
        keywords: ["working memory", "agent"],
        score: 82,
        accepted: true,
        note: "Searched academic papers and official documents.",
      },
    },
  },
];

class StoredClient implements LessonClient {
  readonly mode = "fixture" as const;

  constructor(private readonly rows: ChatMessage[] = messages) {}

  async getLessonBundle(): Promise<LessonBundle> {
    return { chapters: [], summaries: [], snippets: [], starter_questions: [], fixture_data: false };
  }

  async ensureThread(): Promise<ChatThread> {
    return thread;
  }

  async readThread(): Promise<ChatThread | null> {
    return thread;
  }

  async listMessages(): Promise<ChatMessage[]> {
    return this.rows;
  }

  async postMessage(): Promise<PostChatResult> {
    throw new Error("unused");
  }
}

afterEach(() => {
  resetLessonClient();
});

describe("ChatPanel", () => {
  it("renders messages returned by the client as cards", async () => {
    resetLessonClient(new StoredClient());
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ChatPanel videoId="video-1" transcriptAccess starterQuestions={[]} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("From the lesson")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What it is" })).toBeInTheDocument();
    expect(screen.getByText("Stored lesson card.")).toBeInTheDocument();
    expect(screen.getByText("What is an agent?")).toBeInTheDocument();
    expect(screen.getAllByText("Web search on").length).toBeGreaterThan(0);
    expect(screen.getByText("working memory")).toBeInTheDocument();
    expect(screen.getByText("Score 82")).toBeInTheDocument();
    expect(screen.getByText("Searched academic papers and official documents.")).toBeInTheDocument();
    expect(screen.queryByText(/###/)).not.toBeInTheDocument();
  });

  it("renders the withheld state with a retry", async () => {
    const withheld = asTutorAnswer({
      v: 1,
      lesson: [{ heading: "Not answered", body: "Not answered." }],
      external: [],
      sources: [],
      review_status: "withheld",
    });
    const user = messages[0];
    const assistant = messages[1];
    if (!user || !assistant || !withheld) throw new Error("fixture");
    expect(withheld.review_status).toBe("withheld");
    resetLessonClient(
      new StoredClient([
        user,
        { ...assistant, content: "Not answered.", content_json: withheld },
      ]),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ChatPanel videoId="video-1" transcriptAccess starterQuestions={[]} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("The reviewer withheld this answer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByText("Not answered.")).toBeInTheDocument();
  });

  it("says web results were off-subject instead of the generic empty note", async () => {
    const answer = asTutorAnswer({
      v: 1,
      lesson: [{ heading: "From the video", body: "Windings set the voltage ratio." }],
      external: [],
      sources: [],
      decision: "lesson_only",
      outside_lane_empty: true,
      outside_off_subject: true,
    });
    const user = messages[0];
    const assistant = messages[1];
    if (!user || !assistant || !answer) throw new Error("fixture");
    expect(answer.outside_off_subject).toBe(true);
    resetLessonClient(
      new StoredClient([
        { ...user, content: "What is a transformer?" },
        { ...assistant, content: "Windings set the voltage ratio.", content_json: answer },
      ]),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ChatPanel videoId="video-1" transcriptAccess starterQuestions={[]} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(OFF_SUBJECT_NOTE)).toBeInTheDocument();
    expect(screen.queryByText("Search is on, and no outside source was kept.")).not.toBeInTheDocument();
    expect(screen.queryByText(/From web search/)).not.toBeInTheDocument();
  });

  it("renders an empty outside search beside the video answer", async () => {
    const answer = asTutorAnswer({
      v: 1,
      lesson: [{ heading: "From the video", body: "Photosynthesis stores energy in leaves." }],
      external: [],
      sources: [],
      decision: "lesson_only",
      outside_lane_empty: true,
    });
    const user = messages[0];
    const assistant = messages[1];
    if (!user || !assistant || !answer) throw new Error("fixture");
    expect(answer.outside_lane_empty).toBe(true);
    resetLessonClient(
      new StoredClient([
        { ...user, content: "How do leaves store energy?" },
        {
          ...assistant,
          content: "Photosynthesis stores energy in leaves.",
          content_json: answer,
        },
      ]),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ChatPanel videoId="video-1" transcriptAccess starterQuestions={[]} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Photosynthesis stores energy in leaves.")).toBeInTheDocument();
    expect(screen.getByText("Search is on, and no outside source was kept.")).toBeInTheDocument();
    expect(screen.getByText("Searched academic papers and official documents.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText(/From web search/)).not.toBeInTheDocument();
  });
});
