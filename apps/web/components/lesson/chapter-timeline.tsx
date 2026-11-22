"use client";

import { EmptyState } from "@/components/patterns/empty-state";
import { Button } from "@/components/ui/button";
import { formatClock } from "@/lib/lesson/citations";
import type { LessonChapter } from "@/lib/lesson/types";
import { cn } from "@/lib/utils";

type ChapterTimelineProps = {
  chapters: LessonChapter[];
  onSeek?: (seconds: number) => void;
  className?: string;
};

export function ChapterTimeline({ chapters, onSeek, className }: ChapterTimelineProps) {
  if (chapters.length === 0) {
    return (
      <EmptyState
        title="No chapters yet"
        description="No verified timestamps for this video."
        className={className}
      />
    );
  }

  return (
    <nav aria-label="Lesson chapters" className={cn("space-y-2", className)}>
      <ol className="space-y-2">
        {chapters.map((chapter, index) => {
          const hasTime =
            chapter.start_ms != null &&
            Number.isFinite(chapter.start_ms) &&
            chapter.start_ms >= 0;
          const seconds = hasTime ? Math.floor(chapter.start_ms! / 1000) : null;
          return (
            <li
              key={chapter.id}
              className="flex items-start justify-between gap-3 rounded-[var(--radius-card)] border border-border bg-surface px-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">
                  <span className="mr-2 text-muted-foreground">{index + 1}.</span>
                  {chapter.title}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {seconds != null
                    ? formatClock(seconds)
                    : "Source available without exact time"}
                </p>
              </div>
              {seconds != null ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onSeek?.(seconds)}
                  aria-label={`Jump to chapter ${chapter.title} at ${formatClock(seconds)}`}
                >
                  Jump
                </Button>
              ) : (
                <span className="shrink-0 text-xs text-muted-foreground">No jump</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
