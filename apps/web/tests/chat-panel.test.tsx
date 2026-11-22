import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ChatPanel } from "@/components/lesson/chat-panel";
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
    },
  },
];

class StoredClient implements LessonClient {
  readonly mode = "fixture" as const;

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
    return messages;
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
    expect(screen.getByText("Search on")).toBeInTheDocument();
    expect(screen.queryByText(/###/)).not.toBeInTheDocument();
  });
});
