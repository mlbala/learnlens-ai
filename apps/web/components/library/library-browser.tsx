"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { FixtureModeBanner } from "@/components/library/fixture-mode-banner";
import { ImportSourceDialog } from "@/components/library/import-source-dialog";
import { LessonControls, isGeminiLesson } from "@/components/library/lesson-controls";
import {
  LibraryToolbar,
  type LibraryStatusFilter,
  type LibraryViewMode,
} from "@/components/library/library-toolbar";
import { PlaylistCoverageBar } from "@/components/library/playlist-coverage";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageHeader } from "@/components/patterns/page-header";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { SourceStatusBadge } from "@/components/patterns/source-status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { displayLessonTitle, lessonSubtitle } from "@/lib/lesson/title";
import { resolveLibraryMode } from "@/lib/library/client";
import { formatDuration } from "@/lib/library/coverage";
import { libraryKeys, usePlaylistsInfinite, useVideosInfinite } from "@/lib/library/query";
import { cn } from "@/lib/utils";

type LibraryBrowserProps = {
  initialKind?: "all" | "videos" | "playlists";
  title?: string;
  description?: string;
};

export function LibraryBrowser({
  initialKind = "all",
  title = "My Library",
  description = "Browse imported videos and playlists with honest ready coverage.",
}: LibraryBrowserProps) {
  const mode = resolveLibraryMode();
  const [view, setView] = useState<LibraryViewMode>("grid");
  const [status, setStatus] = useState<LibraryStatusFilter>("all");
  const searchParams = useSearchParams();
  const urlQuery = searchParams?.get("q") ?? "";
  // Header search writes ?q= onto /videos; it is the same title filter as the toolbar.
  const [query, setQuery] = useState(urlQuery);
  const [kind, setKind] = useState<"all" | "videos" | "playlists">(initialKind);
  const queryClient = useQueryClient();

  useEffect(() => {
    setQuery(urlQuery);
  }, [urlQuery]);

  const refreshLessons = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: [...libraryKeys.all, "videos"] }),
      queryClient.invalidateQueries({ queryKey: libraryKeys.dashboard() }),
    ]);

  const videoQuery = useVideosInfinite({
    status: status === "all" ? undefined : status,
    q: query || undefined,
  });
  const playlistQuery = usePlaylistsInfinite({ q: query || undefined });

  const videos = useMemo(
    () => videoQuery.data?.pages.flatMap((p) => p.items) ?? [],
    [videoQuery.data],
  );
  const playlists = useMemo(
    () => playlistQuery.data?.pages.flatMap((p) => p.items) ?? [],
    [playlistQuery.data],
  );

  const loading =
    (kind !== "playlists" && videoQuery.isLoading) ||
    (kind !== "videos" && playlistQuery.isLoading);
  const error =
    (kind !== "playlists" && videoQuery.isError && videoQuery.error) ||
    (kind !== "videos" && playlistQuery.isError && playlistQuery.error);

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={<ImportSourceDialog />}
      />
      <FixtureModeBanner mode={mode} />

      {initialKind === "all" ? (
        <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Library kind">
          {(
            [
              ["all", "All"],
              ["videos", "Videos"],
              ["playlists", "Playlists"],
            ] as const
          ).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={kind === value ? "default" : "outline"}
              aria-pressed={kind === value}
              onClick={() => setKind(value)}
            >
              {label}
            </Button>
          ))}
        </div>
      ) : null}

      <LibraryToolbar
        view={view}
        onViewChange={setView}
        status={status}
        onStatusChange={setStatus}
        query={query}
        onQueryChange={setQuery}
        hideNeedsTranscript={initialKind === "videos"}
      />

      {loading ? <PageSkeleton /> : null}

      {error ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Could not load library."}
          action={
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                void videoQuery.refetch();
                void playlistQuery.refetch();
              }}
            >
              Retry
            </Button>
          }
        />
      ) : null}

      {!loading && !error ? (
        <div className="space-y-8">
          {kind !== "playlists" ? (
            <section aria-labelledby="videos-heading">
              <h2 id="videos-heading" className="mb-3 text-lg font-semibold">
                Videos
              </h2>
              {videos.length === 0 ? (
                <EmptyState
                  title="No videos match"
                  description="Paste a public YouTube link, or clear the filters."
                  action={<ImportSourceDialog triggerLabel="Import video" />}
                />
              ) : (
                <ul
                  className={cn(
                    view === "grid"
                      ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
                      : "flex flex-col gap-2",
                  )}
                >
                  {videos.map((video) => {
                    const lessonTitle = displayLessonTitle(video.title);
                    const subtitle = lessonSubtitle({
                      channel: video.channel_title,
                      duration: formatDuration(video.duration_seconds),
                      extra: video.fixture_data ? "Fixture data" : null,
                    });
                    return (
                      <li
                        key={video.id}
                        className={cn(
                          "flex rounded-[var(--radius-card)] border border-border bg-surface transition-colors hover:bg-surface-muted",
                          view === "list"
                            ? "items-center gap-3 px-4 py-3"
                            : "flex-col gap-3 p-4",
                        )}
                      >
                        <Link
                          href={`/videos/${video.id}`}
                          className="block min-w-0 flex-1 rounded-[var(--radius-control)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          aria-label={`Open ${lessonTitle}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate font-medium text-foreground">{lessonTitle}</p>
                              {subtitle ? (
                                <p className="mt-1 truncate text-xs text-muted-foreground">
                                  {subtitle}
                                </p>
                              ) : null}
                            </div>
                            <SourceStatusBadge status={video.status} />
                          </div>
                        </Link>
                        {isGeminiLesson(video) ? (
                          <LessonControls
                            videoId={video.id}
                            title={lessonTitle}
                            pinned={Boolean(video.pinned)}
                            onChanged={() => void refreshLessons()}
                          />
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
              {videoQuery.hasNextPage ? (
                <Button
                  type="button"
                  variant="outline"
                  className="mt-4"
                  disabled={videoQuery.isFetchingNextPage}
                  onClick={() => void videoQuery.fetchNextPage()}
                >
                  {videoQuery.isFetchingNextPage ? "Loading…" : "Load more videos"}
                </Button>
              ) : null}
            </section>
          ) : null}

          {kind !== "videos" ? (
            <section aria-labelledby="playlists-heading">
              <h2 id="playlists-heading" className="mb-3 text-lg font-semibold">
                Playlists
              </h2>
              {playlists.length === 0 ? (
                <EmptyState
                  title="No playlists yet"
                  description="Playlist import is not available yet. Add a single public YouTube video instead."
                />
              ) : (
                <ul
                  className={cn(
                    view === "grid"
                      ? "grid gap-4 lg:grid-cols-2"
                      : "flex flex-col gap-3",
                  )}
                >
                  {playlists.map((playlist) => (
                    <li key={playlist.id}>
                      <Card>
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <CardTitle className="text-base">
                                <Link
                                  href={`/playlists/${playlist.id}`}
                                  className="hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                >
                                  {playlist.title}
                                </Link>
                              </CardTitle>
                              <CardDescription>
                                {playlist.channel_title ?? "Unknown channel"} ·{" "}
                                {playlist.total_items} items
                                {playlist.fixture_data ? " · Fixture data" : ""}
                              </CardDescription>
                            </div>
                            <SourceStatusBadge status={playlist.status === "partial" ? "needs_transcript" : playlist.status} />
                          </div>
                        </CardHeader>
                        <CardContent>
                          <PlaylistCoverageBar coverage={playlist.coverage} compact />
                        </CardContent>
                      </Card>
                    </li>
                  ))}
                </ul>
              )}
              {playlistQuery.hasNextPage ? (
                <Button
                  type="button"
                  variant="outline"
                  className="mt-4"
                  disabled={playlistQuery.isFetchingNextPage}
                  onClick={() => void playlistQuery.fetchNextPage()}
                >
                  {playlistQuery.isFetchingNextPage ? "Loading…" : "Load more playlists"}
                </Button>
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
