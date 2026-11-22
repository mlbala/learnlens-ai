/**
 * Lesson + chat client — fixture demo by default; HTTP when library mode=api.
 * Never exposes API keys; never invents timed citations.
 */

import {
  appendFixtureExchange,
  fixtureGetOrCreateThread,
  fixtureLessonBundle,
  fixtureListMessages,
  fixturePostMessage,
  fixtureThreadScope,
} from "@/lib/lesson/fixtures";
import type {
  ChatMessage,
  ChatThread,
  ExplanationMode,
  LessonBundle,
  LessonChapter,
  LessonSummary,
  PostChatResult,
  TranscriptSnippet,
} from "@/lib/lesson/types";
import { LessonApiError } from "@/lib/lesson/types";
import { getLibraryClient, resolveLibraryMode } from "@/lib/library/client";

export type LessonClientMode = "fixture" | "api";

export interface LessonClient {
  readonly mode: LessonClientMode;
  getLessonBundle(videoId: string): Promise<LessonBundle>;
  ensureThread(videoId: string): Promise<ChatThread>;
  listMessages(threadId: string): Promise<ChatMessage[]>;
  postMessage(input: {
    threadId: string;
    question: string;
    explanationMode: ExplanationMode;
    externalSearch?: boolean;
  }): Promise<PostChatResult>;
}

export class FixtureLessonClient implements LessonClient {
  readonly mode = "fixture" as const;

  async getLessonBundle(videoId: string): Promise<LessonBundle> {
    const video = await getLibraryClient().getVideo(videoId).catch(() => null);
    const generated = video?.metadata_json?.gemini_lesson as
      | { summary?: string; key_points?: string[]; transcript?: string }
      | undefined;
    if (generated && (generated.summary || generated.transcript)) {
      const text = generated.transcript || generated.summary || "";
      const saved = video?.metadata_json?.gemini_segments as
        | {
            id: string;
            ordinal: number;
            text: string;
            start_ms: number | null;
            end_ms: number | null;
            content_hash: string;
          }[]
        | undefined;
      const snippets = saved?.length
        ? saved.map((segment) => ({
            id: segment.id,
            ordinal: segment.ordinal,
            text: segment.text,
            start_ms: segment.start_ms,
            end_ms: segment.end_ms,
            content_hash: segment.content_hash,
            fixture_data: false,
          }))
        : text
            .split(/\n+/)
            .map((line) => line.trim())
            .filter(Boolean)
            .slice(0, 40)
            .map((line, index) => ({
              id: `${videoId}-line-${index}`,
              ordinal: index,
              text: line,
              start_ms: null,
              end_ms: null,
              content_hash: String(index),
              fixture_data: false,
            }));
      return {
        chapters: [],
        summaries: [
          {
            id: `${videoId}-gemini`,
            workspace_id: video?.workspace_id || "",
            scope_kind: "video",
            scope_id: videoId,
            summary_kind: "short",
            revision: 1,
            status: "ready",
            summary: generated.summary || text,
            key_points: generated.key_points || [],
            claims: [],
            examples: [],
            evidence_segment_ids: [],
            origin: "gemini_youtube",
            fixture_data: false,
          },
        ],
        snippets,
        starter_questions: (generated.key_points || []).slice(0, 3),
        fixture_data: false,
      };
    }
    if (!video?.transcript_access) {
      return {
        chapters: [],
        summaries: [],
        snippets: [],
        starter_questions: [],
        fixture_data: true,
      };
    }
    return (
      fixtureLessonBundle(videoId) ?? {
        chapters: [],
        summaries: [],
        snippets: [],
        starter_questions: [],
        fixture_data: true,
      }
    );
  }

  async ensureThread(videoId: string): Promise<ChatThread> {
    return fixtureGetOrCreateThread(videoId);
  }

  async listMessages(threadId: string): Promise<ChatMessage[]> {
    return fixtureListMessages(threadId);
  }

  async postMessage(input: {
    threadId: string;
    question: string;
    explanationMode: ExplanationMode;
    externalSearch?: boolean;
  }): Promise<PostChatResult> {
    try {
      const videoId = fixtureThreadScope(input.threadId);
      const video = videoId ? await getLibraryClient().getVideo(videoId).catch(() => null) : null;
      const lesson = video?.metadata_json?.gemini_lesson as
        | { transcript?: string; summary?: string }
        | undefined;
      const transcript = lesson?.transcript || lesson?.summary || "";
      if (transcript) {
        const res = await fetch("/api/gemini-ask", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            question: input.question,
            transcript,
            title: video?.title,
            explanationMode: input.explanationMode,
            externalSearch: Boolean(input.externalSearch),
          }),
        });
        const body = (await res.json().catch(() => null)) as { answer?: string; error?: string } | null;
        if (!res.ok || !body?.answer) {
          throw new LessonApiError(res.status || 502, "GEMINI_ASK_FAILED", body?.error || "Gemini could not answer.");
        }
        return appendFixtureExchange({
          threadId: input.threadId,
          question: input.question,
          answer: body.answer,
          explanationMode: input.explanationMode,
        });
      }
      return fixturePostMessage({
        threadId: input.threadId,
        question: input.question,
        explanationMode: input.explanationMode,
      });
    } catch (err) {
      const e = err as { code?: string; status?: number; message?: string };
      throw new LessonApiError(
        e.status ?? 500,
        e.code ?? "CHAT_ERROR",
        e.message ?? "Chat request failed",
      );
    }
  }
}

export class HttpLessonClient implements LessonClient {
  readonly mode = "api" as const;

  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });
    const body = (await res.json().catch(() => null)) as
      | T
      | { error?: { code?: string; message?: string; request_id?: string } }
      | null;
    if (!res.ok) {
      const err = body && typeof body === "object" && "error" in body ? body.error : undefined;
      throw new LessonApiError(
        res.status,
        err?.code ?? "HTTP_ERROR",
        err?.message ?? `Request failed (${res.status})`,
        err?.request_id,
      );
    }
    return body as T;
  }

  async getLessonBundle(videoId: string): Promise<LessonBundle> {
    const [chaptersRes, summariesRes] = await Promise.all([
      this.request<{ items: LessonChapter[] }>(`/api/v1/videos/${videoId}/chapters`).catch(
        () => ({ items: [] as LessonChapter[] }),
      ),
      this.request<{ items: LessonSummary[]; blocked?: boolean }>(
        `/api/v1/videos/${videoId}/summaries?ensure=false`,
      ).catch(() => ({ items: [] as LessonSummary[] })),
    ]);

    const chapters = chaptersRes.items.map((c) => ({
      ...c,
      start_ms: chapterStartMs(c),
    }));

    const snippets: TranscriptSnippet[] = [];
    const starters = deriveStarters(summariesRes.items);

    return {
      chapters,
      summaries: summariesRes.items,
      snippets,
      starter_questions: starters,
      fixture_data: false,
    };
  }

  async ensureThread(videoId: string): Promise<ChatThread> {
    const csrf = readCookie("ll_csrf");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (csrf) headers["X-CSRF-Token"] = csrf;
    return this.request<ChatThread>("/api/v1/chat/threads", {
      method: "POST",
      headers,
      body: JSON.stringify({
        scope_kind: "video",
        scope_id: videoId,
        title: "Lesson chat",
      }),
    });
  }

  async listMessages(threadId: string): Promise<ChatMessage[]> {
    const data = await this.request<{ items: ChatMessage[] }>(
      `/api/v1/chat/threads/${threadId}/messages?limit=100`,
    );
    return data.items;
  }

  async postMessage(input: {
    threadId: string;
    question: string;
    explanationMode: ExplanationMode;
    externalSearch?: boolean;
  }): Promise<PostChatResult> {
    const csrf = readCookie("ll_csrf");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (csrf) headers["X-CSRF-Token"] = csrf;
    return this.request<PostChatResult>(`/api/v1/chat/threads/${input.threadId}/messages`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        question: input.question,
        explanation_mode: input.explanationMode,
      }),
    });
  }
}

function chapterStartMs(chapter: LessonChapter): number | null {
  const topic = chapter.topic_json;
  if (topic && typeof topic === "object") {
    const ms = topic.start_ms;
    if (typeof ms === "number" && Number.isFinite(ms) && ms >= 0) return ms;
  }
  return chapter.start_ms ?? null;
}

function deriveStarters(summaries: LessonSummary[]): string[] {
  const short = summaries.find((s) => s.summary_kind === "short");
  const points = short?.key_points?.filter(Boolean).slice(0, 3) ?? [];
  return points.map((p) => `Explain: ${p}`);
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

let singleton: LessonClient | null = null;

export function getLessonClient(): LessonClient {
  if (singleton) return singleton;
  const mode = resolveLibraryMode();
  singleton = mode === "api" ? new HttpLessonClient("") : new FixtureLessonClient();
  return singleton;
}

/** Test helper — reset singleton between Vitest cases. */
export function resetLessonClient(client?: LessonClient): void {
  singleton = client ?? null;
}
