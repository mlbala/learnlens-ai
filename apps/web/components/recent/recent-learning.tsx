"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { ImportSourceDialog } from "@/components/library/import-source-dialog";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageHeader } from "@/components/patterns/page-header";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { Button } from "@/components/ui/button";
import { useVideosInfinite } from "@/lib/library/query";
import type { VideoRecord } from "@/lib/library/types";

type RecentLearningListProps = {
  lessons: VideoRecord[];
  emptyAction?: ReactNode;
};

export function RecentLearningList({ lessons, emptyAction }: RecentLearningListProps) {
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
      {lessons.map((lesson) => (
        <li key={lesson.id}>
          <Link
            href={`/videos/${lesson.id}`}
            className="block rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3 transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Open ${lesson.title}`}
          >
            <p className="truncate font-medium text-foreground">{lesson.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {lesson.channel_title ?? "Channel unavailable"}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function RecentLearning() {
  const query = useVideosInfinite({ limit: 100 });
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
          emptyAction={<ImportSourceDialog triggerLabel="Paste a YouTube link" />}
        />
      ) : null}
    </>
  );
}
