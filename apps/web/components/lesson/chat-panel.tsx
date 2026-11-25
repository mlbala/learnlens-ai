"use client";

import {
  ArrowUp,
  BookOpen,
  ChevronRight,
  Globe,
  LoaderCircle,
  MessageCircleQuestion,
  Sparkles,
} from "lucide-react";
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

function safeFailure(error: unknown, fallback: string): string {
  if (error instanceof LessonApiError) {
    if (error.code === "GEMINI_BUSY" || error.code === "PROVIDER_TEMPORARILY_UNAVAILABLE") {
      return "Gemini is busy.";
    }
    if (error.code === "LESSON_NOT_IN_WORKSPACE") {
      return "This lesson is not in this workspace.";
    }
    if (isPublicSentence(error.message)) return error.message;
    return fallback;
  }
  if (error instanceof Error && isPublicSentence(error.message)) return error.message;
  return fallback;
}

function isPublicSentence(message: string): boolean {
  const text = message.trim();
  if (!text || text.length > 240) return false;
  if (/traceback|api[_-]?key|stack trace|exception/i.test(text)) return false;
  if (text.includes("{") || text.includes("\n")) return false;
  return true;
}

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
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const threadQuery = useLessonThread(videoId, { enabled: transcriptAccess });
  const threadId = threadQuery.data?.id;
  const messagesQuery = useChatMessages(threadId);
  const post = usePostChatMessage(videoId);

  useEffect(() => {
    if (draftQuestion) {
      setQuestion(draftQuestion);
      onDraftConsumed?.();
      inputRef.current?.focus();
    }
  }, [draftQuestion, onDraftConsumed]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [question]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else {
      el.scrollTop = el.scrollHeight;
    }
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
        message={safeFailure(threadQuery.error, "Could not open a chat thread.")}
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
      setLastError(safeFailure(err, "The answer could not be completed."));
    } finally {
      setPendingLocal(false);
    }
  }

  const showWelcome = messages.length === 0 && !busy && !threadQuery.isLoading;

  return (
    <div
      className={cn(
        "flex h-full min-h-[28rem] flex-col overflow-hidden rounded-[var(--radius-panel)] border border-border bg-surface shadow-[var(--shadow-md)]",
        className,
      )}
    >
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <TutorAvatar />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">Ask AI</p>
          <p className="truncate text-xs text-muted-foreground">Answers grounded in this lesson</p>
        </div>
        <Badge variant={externalSearch ? "info" : "secondary"}>
          {externalSearch ? <Globe className="h-3 w-3" aria-hidden /> : <BookOpen className="h-3 w-3" aria-hidden />}
          {externalSearch ? "Web search on" : "Lesson only"}
        </Badge>
      </header>

      <div
        ref={listRef}
        className="scroll-quiet min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
      >
        {threadQuery.isLoading || (Boolean(threadId) && messagesQuery.isLoading && messages.length === 0) ? (
          <p className="text-sm text-muted-foreground">Loading conversation…</p>
        ) : null}

        {showWelcome ? (
          <div className="flex flex-col items-center px-2 pt-4 text-center animate-rise">
            <div className="bg-brand flex h-12 w-12 items-center justify-center rounded-2xl text-white shadow-[var(--shadow-md)]">
              <Sparkles className="h-6 w-6" aria-hidden />
            </div>
            <h3 className="mt-4 text-base font-semibold text-foreground">What do you want to understand?</h3>
            <p className="mt-1 max-w-xs text-sm text-muted-foreground">
              Ask about any idea in this lesson. Answers cite the moments they come from.
            </p>
            <div className="mt-5 w-full space-y-2 text-left">
              <p className="text-xs font-medium text-muted-foreground">
                Starter questions from available evidence
              </p>
              {starterQuestions.length > 0 ? (
                starterQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="group flex w-full items-center gap-3 rounded-[var(--radius-card)] border border-border bg-surface px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:border-primary/40 hover:bg-primary/5 disabled:opacity-50"
                    onClick={() => void send(q)}
                    disabled={busy || !composerReady}
                  >
                    <MessageCircleQuestion className="h-4 w-4 shrink-0 text-primary" aria-hidden />
                    <span className="flex-1">{q}</span>
                    <ChevronRight
                      className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                      aria-hidden
                    />
                  </button>
                ))
              ) : (
                <p className="text-xs text-muted-foreground">
                  No starter prompts yet — ask a question about the transcript evidence.
                </p>
              )}
            </div>
          </div>
        ) : null}

        {messages.map((msg, index) => (
          <ChatBubble
            key={msg.id}
            message={msg}
            youtubeVideoId={youtubeVideoId}
            onSeek={onSeek}
            onRetry={
              msg.role === "assistant"
                ? () => {
                    const prior = messages
                      .slice(0, index)
                      .reverse()
                      .find((item) => item.role === "user");
                    if (prior?.content.trim()) void send(prior.content);
                  }
                : undefined
            }
          />
        ))}
        {busy ? (
          <div className="flex items-start gap-3 animate-rise" data-testid="chat-pending">
            <TutorAvatar />
            <div className="min-w-0 rounded-2xl rounded-tl-md border border-border bg-surface-muted px-3.5 py-2.5">
              <span className="flex items-center gap-1 text-primary" aria-hidden>
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </span>
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
                {externalSearch
                  ? "Reading this lesson, checking search words, then looking through papers and official documents…"
                  : "Writing a detailed explanation from the lesson…"}
              </p>
            </div>
          </div>
        ) : null}
      </div>

      {lastError ? (
        <div className="px-4 pb-2">
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
        </div>
      ) : null}

      <form
        className="border-t border-border bg-surface-muted/40 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(question);
        }}
      >
        <div className="rounded-[var(--radius-card)] border border-border bg-surface shadow-[var(--shadow-sm)] transition-shadow focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-ring/20">
          <Label htmlFor={questionId} className="sr-only">
            Ask about this lesson
          </Label>
          <textarea
            ref={inputRef}
            id={questionId}
            rows={1}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void send(question);
              }
            }}
            disabled={busy || !composerReady}
            placeholder="Ask about this lesson…"
            className="block max-h-40 min-h-[2.75rem] w-full resize-none bg-transparent px-3.5 pt-3 pb-1 text-sm leading-6 text-foreground placeholder:text-muted-foreground focus-visible:outline-none disabled:opacity-60"
          />
          <div className="flex flex-wrap items-center gap-2 px-2 pb-2 pt-1">
            <div
              role="group"
              aria-labelledby={modeId}
              className="inline-flex items-center rounded-full border border-border bg-surface-muted p-0.5"
            >
              <span id={modeId} className="sr-only">
                Explanation
              </span>
              {MODES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  aria-pressed={mode === item.value}
                  disabled={busy}
                  onClick={() => setMode(item.value)}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50",
                    mode === item.value
                      ? "bg-surface text-foreground shadow-[var(--shadow-sm)]"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <label
              htmlFor={searchId}
              title="Reads this lesson, writes search words, and scores them before looking through academic papers and official documents."
              className={cn(
                "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                externalSearch
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-border bg-surface text-muted-foreground hover:text-foreground",
                busy && "pointer-events-none opacity-50",
              )}
            >
              <input
                id={searchId}
                type="checkbox"
                className="sr-only"
                checked={externalSearch}
                onChange={(e) => setExternalSearch(e.target.checked)}
                disabled={busy}
              />
              <Globe className="h-3.5 w-3.5" aria-hidden />
              Web search
            </label>
            <Button
              type="submit"
              size="icon"
              aria-label="Send"
              className="ml-auto h-9 min-h-9 w-9 rounded-full"
              disabled={busy || !composerReady || !question.trim()}
            >
              {busy ? <LoaderCircle className="animate-spin" aria-hidden /> : <ArrowUp aria-hidden />}
            </Button>
          </div>
        </div>
        <p className="mt-2 px-1 text-[11px] leading-4 text-muted-foreground">
          {externalSearch
            ? "Web search is on. Search words are checked against this lesson before the answer."
            : "Lesson only. Turn on web search to add papers and official documents."}
          <span className="hidden sm:inline"> · Enter to send, Shift+Enter for a new line.</span>
        </p>
      </form>
    </div>
  );
}

function TutorAvatar() {
  return (
    <span
      className="bg-brand flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white shadow-[var(--shadow-sm)]"
      aria-hidden
    >
      <Sparkles className="h-4 w-4" />
    </span>
  );
}

export const OFF_SUBJECT_NOTE =
  "Web results were about a different subject than this video, so none are shown.";

function ChatBubble({
  message,
  youtubeVideoId,
  onSeek,
  onRetry,
}: {
  message: ChatMessage;
  youtubeVideoId?: string | null;
  onSeek?: (seconds: number) => void;
  onRetry?: () => void;
}) {
  const isUser = message.role === "user";
  const withheld = message.content_json?.review_status === "withheld";
  const searchRejected = message.content_json?.web_search?.accepted === false;
  const offSubject = !searchRejected && message.content_json?.outside_off_subject === true;
  const outsideEmpty =
    !searchRejected &&
    !offSubject &&
    message.content_json?.outside_lane_empty === true &&
    (message.content_json.lesson?.length ?? 0) > 0;
  const modeLabel =
    message.explanation_mode === "simple"
      ? "Brief"
      : message.explanation_mode === "technical"
        ? "Technical"
        : message.explanation_mode
          ? "Detailed"
          : null;

  if (isUser) {
    return (
      <div className="flex flex-col items-end gap-1 animate-rise" data-role={message.role}>
        <span className="sr-only">You</span>
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2.5 text-primary-foreground shadow-[var(--shadow-sm)]">
          <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        </div>
        {typeof message.external_search_enabled === "boolean" ? (
          <span className="flex items-center gap-1 pr-1 text-[11px] text-muted-foreground">
            {message.external_search_enabled ? (
              <Globe className="h-3 w-3" aria-hidden />
            ) : (
              <BookOpen className="h-3 w-3" aria-hidden />
            )}
            {message.external_search_enabled ? "Web search on" : "Lesson only"}
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 animate-rise" data-role={message.role}>
      <TutorAvatar />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-foreground">Tutor</span>
          {message.confidence_label && message.confidence_label !== "model" ? (
            <Badge variant={message.unsupported ? "warning" : "success"}>
              {message.unsupported ? "not covered" : message.confidence_label}
            </Badge>
          ) : null}
          {modeLabel ? <Badge variant="secondary">{modeLabel}</Badge> : null}
        </div>
        {withheld ? (
          <Alert>
            <AlertDescription className="flex flex-wrap items-center gap-2">
              <span>The reviewer withheld this answer.</span>
              {onRetry ? (
                <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                  Retry
                </Button>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}
        {offSubject ? (
          <Alert>
            <AlertDescription>{OFF_SUBJECT_NOTE}</AlertDescription>
          </Alert>
        ) : null}
        {outsideEmpty ? (
          <Alert>
            <AlertDescription className="flex flex-wrap items-center gap-2">
              <span>Search is on, and no outside source was kept.</span>
              {onRetry ? (
                <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                  Retry
                </Button>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}
        <AnswerView content={message.content} structured={message.content_json} />

        {message.analogies.length > 0 ? (
          <div className="space-y-2">
            {message.analogies.map((a) => (
              <div
                key={a.text}
                className="rounded-[var(--radius-card)] border border-dashed border-warning/40 bg-warning/5 px-3 py-2"
              >
                <Badge variant="warning" className="mb-1">
                  AI-created analogy
                </Badge>
                <p className="text-xs leading-5 text-muted-foreground">{a.text}</p>
              </div>
            ))}
          </div>
        ) : null}

        {message.citations.length > 0 ? (
          <details className="group rounded-[var(--radius-card)] border border-border bg-surface-muted/50">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs font-medium text-primary [&::-webkit-details-marker]:hidden">
              <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" aria-hidden />
              Supporting moments ({message.citations.length})
            </summary>
            <div className="space-y-2 px-3 pb-3">
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
    </div>
  );
}
