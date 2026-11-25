"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";

import { ImportSourceDialog } from "@/components/library/import-source-dialog";
import { LessonControls, isGeminiLesson } from "@/components/library/lesson-controls";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageHeader } from "@/components/patterns/page-header";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { Button } from "@/components/ui/button";
import { displayLessonTitle, lessonSubtitle } from "@/lib/lesson/title";
import { libraryKeys, useVideosInfinite } from "@/lib/library/query";
import type { VideoRecord } from "@/lib/library/types";

type RecentLearningListProps = {
  lessons: VideoRecord[];
  emptyAction?: ReactNode;
  /** Refresh the list after Pin or Remove. */
  onChanged?: () => void;
};

export function RecentLearningList({ lessons, emptyAction, onChanged }: RecentLearningListProps) {
  if (lessons.length === 0) {
    return (
      <EmptyState
        title="No recent lessons"
        description="Paste a public YouTube link to build a lesson. It is saved for My Library and Recent Learning."
        action={emptyAction}
      />
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {lessons.map((lesson) => {
        const title = displayLessonTitle(lesson.title);
        const subtitle = lessonSubtitle({ channel: lesson.channel_title });
        return (
          <li
            key={lesson.id}
            className="flex items-center gap-3 rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3 transition-colors hover:bg-surface-muted"
          >
            <Link
              href={`/videos/${lesson.id}`}
              className="block min-w-0 flex-1 rounded-[var(--radius-control)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Open ${title}`}
            >
              <p className="truncate font-medium text-foreground">{title}</p>
              {subtitle ? (
                <p className="mt-1 truncate text-xs text-muted-foreground">{subtitle}</p>
              ) : null}
            </Link>
            {isGeminiLesson(lesson) ? (
              <LessonControls
                videoId={lesson.id}
                title={title}
                pinned={Boolean(lesson.pinned)}
                onChanged={onChanged}
              />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function RecentLearning() {
  const query = useVideosInfinite({ limit: 100 });
  const queryClient = useQueryClient();
  const lessons = query.data?.pages.flatMap((page) => page.items) ?? [];
  const error = query.isError ? query.error : null;

  return (
    <>
      <PageHeader
        title="Recent Learning"
        description="The same saved lessons as My Library, newest first."
      />
      {query.isLoading ? <PageSkeleton /> : null}
      {error ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Could not load recent lessons."}
          action={
            <Button type="button" variant="outline" onClick={() => void query.refetch()}>
              Retry
            </Button>
          }
        />
      ) : null}
      {!query.isLoading && !error ? (
        <RecentLearningList
          lessons={lessons}
          onChanged={() => {
            void queryClient.invalidateQueries({ queryKey: [...libraryKeys.all, "videos"] });
            void queryClient.invalidateQueries({ queryKey: libraryKeys.dashboard() });
          }}
          emptyAction={<ImportSourceDialog triggerLabel="Paste a YouTube link" />}
        />
      ) : null}
    </>
  );
}
