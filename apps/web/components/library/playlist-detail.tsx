"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { CourseOverview } from "@/components/library/course-overview";
import { FixtureModeBanner } from "@/components/library/fixture-mode-banner";
import { PlaylistCoverageBar } from "@/components/library/playlist-coverage";
import { VideoLessonRow } from "@/components/library/video-lesson-row";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageHeader } from "@/components/patterns/page-header";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { Button } from "@/components/ui/button";
import { resolveLibraryMode } from "@/lib/library/client";
import {
  usePlaylist,
  usePlaylistCourseSummary,
  useSynthesizePlaylist,
} from "@/lib/library/query";

type PlaylistDetailProps = {
  playlistId: string;
};

type ItemFilter = "all" | "ready" | "needs_transcript" | "unavailable" | "failed";

export function PlaylistDetail({ playlistId }: PlaylistDetailProps) {
  const mode = resolveLibraryMode();
  const query = usePlaylist(playlistId);
  const courseQuery = usePlaylistCourseSummary(playlistId);
  const synthesize = useSynthesizePlaylist();
  const [filter, setFilter] = useState<ItemFilter>("all");

  const items = useMemo(() => {
    const all = query.data?.items ?? [];
    if (filter === "all") return all;
    if (filter === "failed") {
      return all.filter((i) => i.state === "failed" || i.state === "failed_retryable");
    }
    return all.filter((i) => i.state === filter);
  }, [query.data, filter]);

  if (query.isLoading) return <PageSkeleton />;

  if (query.isError) {
    return (
      <ErrorState
        title="Playlist unavailable"
        message={query.error instanceof Error ? query.error.message : "Not found"}
        action={
          <Button type="button" variant="outline" onClick={() => void query.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  const playlist = query.data;
  if (!playlist) return null;

  return (
    <>
      <PageHeader
        title={playlist.title}
        description={`${playlist.channel_title ?? "Unknown channel"} · ${playlist.total_items} ordered items${playlist.fixture_data ? " · Fixture data" : ""}`}
        actions={
          <Button asChild variant="outline">
            <Link href="/playlists">Back to playlists</Link>
          </Button>
        }
      />
      <FixtureModeBanner mode={mode} />

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          <PlaylistCoverageBar coverage={playlist.coverage} />

          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter playlist items">
            {(
              [
                ["all", "All"],
                ["ready", "Ready"],
                ["needs_transcript", "Needs transcript"],
                ["unavailable", "Unavailable"],
                ["failed", "Failed"],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={filter === value ? "default" : "outline"}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {label}
              </Button>
            ))}
          </div>

          {items.length === 0 ? (
            <EmptyState
              title="No items in this filter"
              description="Missing videos never receive invented chapter descriptions."
            />
          ) : (
            <ol className="space-y-2" aria-label="Ordered playlist videos">
              {items.map((item) => (
                <li key={item.id}>
                  <VideoLessonRow item={item} />
                </li>
              ))}
            </ol>
          )}
        </div>

        <aside className="space-y-4 lg:col-span-4">
          <CourseOverview
            summary={courseQuery.data}
            loading={courseQuery.isLoading}
            synthesizing={synthesize.isPending}
            onSynthesize={() => {
              void synthesize.mutateAsync(playlistId).then(() => courseQuery.refetch());
            }}
          />
        </aside>
      </div>
    </>
  );
}
