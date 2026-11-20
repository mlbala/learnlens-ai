"use client";

import { EmptyState } from "@/components/patterns/empty-state";
import { Button } from "@/components/ui/button";
import { formatClock } from "@/lib/lesson/citations";
import type { TranscriptSnippet } from "@/lib/lesson/types";
import { cn } from "@/lib/utils";

type TranscriptPanelProps = {
  snippets: TranscriptSnippet[];
  onSeek?: (seconds: number) => void;
  className?: string;
};

export function TranscriptPanel({ snippets, onSeek, className }: TranscriptPanelProps) {
  if (snippets.length === 0) {
    return (
      <EmptyState
        title="No transcript snippets"
        description="Snippet panel shows permitted uploaded segments only. API mode may omit snippets until a segment list endpoint is wired; fixture mode includes synthetic samples."
        className={className}
      />
    );
  }

  return (
    <div
      className={cn(
        "max-h-[28rem] space-y-2 overflow-y-auto rounded-[var(--radius-card)] border border-border bg-surface p-3",
        className,
      )}
      role="region"
      aria-label="Transcript snippets"
      tabIndex={0}
    >
      {snippets.map((snip) => {
        const timed =
          snip.start_ms != null && Number.isFinite(snip.start_ms) && snip.start_ms >= 0;
        const seconds = timed ? Math.floor(snip.start_ms! / 1000) : null;
        return (
          <article
            key={snip.id}
            className="rounded-[var(--radius-control)] border border-border/70 bg-surface-muted/40 px-3 py-2"
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                {seconds != null ? formatClock(seconds) : "No exact time"}
              </span>
              {seconds != null ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => onSeek?.(seconds)}
                  aria-label={`Seek to transcript at ${formatClock(seconds)}`}
                >
                  Jump
                </Button>
              ) : (
                <span className="text-xs text-muted-foreground">
                  Source available without exact time
                </span>
              )}
            </div>
            <p className="text-sm leading-relaxed text-foreground">{snip.text}</p>
          </article>
        );
      })}
    </div>
  );
}
