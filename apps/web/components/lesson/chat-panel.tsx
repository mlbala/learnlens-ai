"use client";

import { useEffect, useId, useRef, useState } from "react";

import { AnswerView } from "@/components/lesson/answer-view";
import { EvidenceCitation } from "@/components/lesson/evidence-citation";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  useChatMessages,
  useLessonThread,
  usePostChatMessage,
} from "@/lib/lesson/query";
import type { ChatMessage, ExplanationMode } from "@/lib/lesson/types";
import { LessonApiError } from "@/lib/lesson/types";
import { cn } from "@/lib/utils";

type ChatPanelProps = {
  videoId: string;
  youtubeVideoId?: string | null;
  transcriptAccess: boolean;
  starterQuestions: string[];
  draftQuestion?: string | null;
  onDraftConsumed?: () => void;
  onSeek?: (seconds: number) => void;
  className?: string;
};

const MODES: { value: ExplanationMode; label: string }[] = [
  { value: "simple", label: "Brief" },
  { value: "standard", label: "Detailed" },
  { value: "technical", label: "Technical" },
];

export function ChatPanel({
  videoId,
  youtubeVideoId,
  transcriptAccess,
  starterQuestions,
  draftQuestion,
  onDraftConsumed,
  onSeek,
  className,
}: ChatPanelProps) {
  const questionId = useId();
  const modeId = useId();
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<ExplanationMode>("standard");
  const [externalSearch, setExternalSearch] = useState(true);
  const searchId = useId();
  const [pendingLocal, setPendingLocal] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const threadQuery = useLessonThread(videoId, { enabled: transcriptAccess });
  const threadId = threadQuery.data?.id;
  const messagesQuery = useChatMessages(threadId);
  const post = usePostChatMessage(videoId);

  useEffect(() => {
    if (draftQuestion) {
      setQuestion(draftQuestion);
      onDraftConsumed?.();
    }
  }, [draftQuestion, onDraftConsumed]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messagesQuery.data, pendingLocal]);

  if (!transcriptAccess) {
    return (
      <EmptyState
        title="Ask AI unavailable"
        description="Upload a permitted transcript before asking grounded questions. A URL alone never yields knowledge."
        className={className}
      />
    );
  }

  if (threadQuery.isError) {
    return (
      <ErrorState
        title="Chat unavailable"
        message={
          threadQuery.error instanceof Error
            ? threadQuery.error.message
            : "Could not open a chat thread."
        }
        action={
          <Button type="button" variant="outline" onClick={() => void threadQuery.refetch()}>
            Retry
          </Button>
        }
        className={className}
      />
    );
  }

  const messages = messagesQuery.data ?? [];
  const busy = pendingLocal || post.isPending;
  const composerReady = !threadQuery.isLoading && !threadQuery.isError;

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || !composerReady || busy) return;
    setLastError(null);
    setPendingLocal(true);
    try {
      await post.mutateAsync({
        threadId: threadId ?? "",
        question: trimmed,
        explanationMode: mode,
        externalSearch,
      });
      setQuestion("");
      await messagesQuery.refetch();
    } catch (err) {
      const message =
        err instanceof LessonApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Chat request failed";
      setLastError(message);
    } finally {
      setPendingLocal(false);
    }
  }

  return (
    <div className={cn("flex h-full min-h-[24rem] flex-col gap-3", className)}>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[10rem] flex-1 space-y-1.5">
          <Label htmlFor={modeId}>Explanation mode</Label>
          <select
            id={modeId}
            className="h-10 w-full rounded-[var(--radius-control)] border border-border bg-surface px-3 text-sm text-foreground"
            value={mode}
            onChange={(e) => setMode(e.target.value as ExplanationMode)}
            disabled={busy}
          >
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <label htmlFor={searchId} className="flex min-h-10 items-center gap-2 pb-1 text-sm text-foreground">
          <input
            id={searchId}
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={externalSearch}
            onChange={(e) => setExternalSearch(e.target.checked)}
            disabled={busy}
          />
          Search academic papers and official docs
        </label>
      </div>

      {messages.length === 0 && !busy ? (
        <div className="space-y-2 rounded-[var(--radius-card)] border border-dashed border-border bg-surface p-3">
          <p className="text-xs font-medium text-muted-foreground">
            Starter questions from available evidence
          </p>
          <div className="flex flex-col gap-2">
            {starterQuestions.length > 0 ? (
              starterQuestions.map((q) => (
                <Button
                  key={q}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-auto justify-start whitespace-normal py-2 text-left"
                  onClick={() => void send(q)}
                  disabled={busy || !composerReady}
                >
                  {q}
                </Button>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                No starter prompts yet — ask a question about the transcript evidence.
              </p>
            )}
          </div>
        </div>
      ) : null}

      <div
        ref={listRef}
        className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-[var(--radius-card)] border border-border bg-surface p-3"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
      >
        {threadQuery.isLoading || (Boolean(threadId) && messagesQuery.isLoading && messages.length === 0) ? (
          <p className="text-sm text-muted-foreground">Loading conversation…</p>
        ) : null}
        {messages.map((msg) => (
          <ChatBubble
            key={msg.id}
            message={msg}
            youtubeVideoId={youtubeVideoId}
            onSeek={onSeek}
          />
        ))}
        {busy ? (
          <div
            className="rounded-[var(--radius-card)] border border-border bg-surface-muted px-3 py-2 text-sm text-muted-foreground"
            data-testid="chat-pending"
          >
            {externalSearch
              ? "Searching papers and official docs, then writing a detailed explanation…"
              : "Writing a detailed explanation from the lesson…"}
          </div>
        ) : null}
      </div>

      {lastError ? (
        <Alert variant="danger">
          <AlertTitle>Chat failed</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>{lastError}</span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setLastError(null);
                if (question.trim()) void send(question);
              }}
            >
              Retry last question
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <form
        className="space-y-2 border-t border-border pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(question);
        }}
      >
        <Label htmlFor={questionId}>Ask about this lesson</Label>
        <textarea
          id={questionId}
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy || !composerReady}
          placeholder="Ask about this lesson…"
          className="w-full resize-y rounded-[var(--radius-control)] border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Detailed answers use the lesson. The checkbox adds papers and official documentation.
          </p>
          <Button type="submit" disabled={busy || !composerReady || !question.trim()}>
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}

function ChatBubble({
  message,
  youtubeVideoId,
  onSeek,
}: {
  message: ChatMessage;
  youtubeVideoId?: string | null;
  onSeek?: (seconds: number) => void;
}) {
  const isUser = message.role === "user";
  return (
    <div
      className={cn(
        "rounded-[var(--radius-card)] px-3 py-2",
        isUser ? "bg-surface-muted text-foreground" : "border border-border bg-surface",
      )}
      data-role={message.role}
    >
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {isUser ? "You" : "Tutor"}
        </span>
        {!isUser && message.confidence_label && message.confidence_label !== "model" ? (
          <Badge variant={message.unsupported ? "warning" : "success"}>
            {message.unsupported ? "not covered" : message.confidence_label}
          </Badge>
        ) : null}
        {isUser && typeof message.external_search_enabled === "boolean" ? (
          <Badge variant="secondary">{message.external_search_enabled ? "Search on" : "Search off"}</Badge>
        ) : null}
        {!isUser && message.explanation_mode ? (
          <Badge variant="secondary">
            {message.explanation_mode === "simple"
              ? "Brief"
              : message.explanation_mode === "technical"
                ? "Technical"
                : "Detailed"}
          </Badge>
        ) : null}
      </div>
      {isUser ? (
        <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">{message.content}</p>
      ) : (
        <AnswerView content={message.content} structured={message.content_json} />
      )}

      {!isUser && message.analogies.length > 0 ? (
        <div className="mt-2 space-y-2">
          {message.analogies.map((a) => (
            <div
              key={a.text}
              className="rounded-[var(--radius-control)] border border-dashed border-border px-2.5 py-2"
            >
              <Badge variant="warning" className="mb-1">
                AI-created analogy
              </Badge>
              <p className="text-xs text-muted-foreground">{a.text}</p>
            </div>
          ))}
        </div>
      ) : null}

      {!isUser && message.citations.length > 0 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-primary">
            Supporting moments ({message.citations.length})
          </summary>
          <div className="mt-2 space-y-2">
            {message.citations.map((c) => (
              <EvidenceCitation
                key={c.citation_id}
                citation={c}
                youtubeVideoId={youtubeVideoId}
                onSeek={onSeek}
              />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
