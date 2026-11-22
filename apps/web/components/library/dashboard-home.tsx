"use client";

import { CircleCheck, FileClock, ListVideo, LoaderCircle, ChevronRight } from "lucide-react";
import Link from "next/link";

import { FixtureModeBanner } from "@/components/library/fixture-mode-banner";
import { ImportSourceDialog } from "@/components/library/import-source-dialog";
import { HealthStatus } from "@/components/HealthStatus";
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
import { useDashboardStats, useVideosInfinite } from "@/lib/library/query";

export function DashboardHome() {
  const mode = resolveLibraryMode();
  const statsQuery = useDashboardStats();
  const recentQuery = useVideosInfinite({ status: undefined, q: undefined });

  const stats = statsQuery.data;
  const recent = recentQuery.data?.pages[0]?.items.slice(0, 4) ?? [];
  const attention = recent.filter((v) =>
    ["failed_retryable", "failed", "failed_terminal", "needs_transcript"].includes(v.status),
  );

  return (
    <>
      <PageHeader
        title="Your learning workspace"
        description="Paste a public YouTube link. Gemini builds the lesson from the video."
        actions={<ImportSourceDialog />}
      />
      <FixtureModeBanner mode={mode} />

      {statsQuery.isLoading ? <PageSkeleton /> : null}

      {statsQuery.isError ? (
        <ErrorState
          message={
            statsQuery.error instanceof Error
              ? statsQuery.error.message
              : "Could not load workspace stats."
          }
          action={
            <Button type="button" variant="outline" onClick={() => void statsQuery.refetch()}>
              Retry
            </Button>
          }
        />
      ) : null}

      {stats ? (
        <section
          aria-label="Workspace overview"
          className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          {[
            { label: "Videos ready", value: stats.videos_ready, Icon: CircleCheck, tone: "text-success bg-success/10" },
            { label: "Playlists", value: stats.playlists, Icon: ListVideo, tone: "text-primary bg-primary/10" },
            { label: "Processing", value: stats.processing, Icon: LoaderCircle, tone: "text-accent bg-accent/10" },
            {
              label: "Pending transcripts",
              value: stats.pending_transcripts,
              Icon: FileClock,
              tone: "text-warning bg-warning/10",
            },
          ].map(({ label, value, Icon, tone }) => (
            <Card key={label} className="hover:shadow-[var(--shadow-md)]">
              <CardHeader className="flex-row items-center gap-4 space-y-0">
                <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-card)] ${tone}`}>
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <div className="min-w-0">
                  <CardDescription>{label}</CardDescription>
                  <CardTitle className="mt-1 text-2xl tabular-nums">{value}</CardTitle>
                </div>
              </CardHeader>
            </Card>
          ))}
        </section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="continue-heading" className="space-y-3">
          <h2 id="continue-heading" className="text-lg font-semibold">
            Continue learning
          </h2>
          {recent.filter((v) => v.status === "ready").length === 0 ? (
            <EmptyState
              title="No ready lessons yet"
              description="Paste a public YouTube link. Gemini builds the lesson from the video."
              action={<ImportSourceDialog triggerLabel="Add source" />}
            />
          ) : (
            <ul className="space-y-2">
              {recent
                .filter((v) => v.status === "ready")
                .map((video) => (
                  <li key={video.id}>
                    <Link
                      href={`/videos/${video.id}`}
                      className="group flex min-h-11 items-center justify-between gap-3 rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3 text-sm shadow-[var(--shadow-sm)] transition-all hover:-translate-y-px hover:border-primary/30 hover:shadow-[var(--shadow-md)]"
                    >
                      <span className="min-w-0 truncate font-medium">{displayLessonTitle(video.title)}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        <SourceStatusBadge status={video.status} />
                        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
                      </span>
                    </Link>
                  </li>
                ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="attention-heading" className="space-y-3">
          <h2 id="attention-heading" className="text-lg font-semibold">
            Jobs needing attention
          </h2>
          {attention.length === 0 ? (
            <EmptyState
              title="Nothing waiting"
              description="Failed or transcript-needed items will appear here."
            />
          ) : (
            <ul className="space-y-2">
              {attention.map((video) => (
                <li key={video.id}>
                  <Link
                    href={`/videos/${video.id}`}
                    className="group flex min-h-11 items-center justify-between gap-3 rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3 text-sm shadow-[var(--shadow-sm)] transition-all hover:-translate-y-px hover:border-primary/30 hover:shadow-[var(--shadow-md)]"
                  >
                    <span className="min-w-0 truncate font-medium">{displayLessonTitle(video.title)}</span>
                    <SourceStatusBadge status={video.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="recent-heading" className="mt-8 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="recent-heading" className="text-lg font-semibold">
            Recently imported
          </h2>
          <Button asChild variant="outline" size="sm">
            <Link href="/library">Open library</Link>
          </Button>
        </div>
        {recent.length === 0 ? (
          <EmptyState
            title="Library is empty"
            description="Paste a public YouTube link. Gemini builds the lesson from the video."
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {recent.map((video) => {
              const subtitle = lessonSubtitle({
                channel: video.channel_title,
                extra: video.fixture_data ? "Fixture data" : null,
              });
              return (
              <li key={video.id}>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">
                      <Link href={`/videos/${video.id}`} className="line-clamp-2 hover:text-primary">
                        {displayLessonTitle(video.title)}
                      </Link>
                    </CardTitle>
                    {subtitle ? (
                      <CardDescription className="truncate">{subtitle}</CardDescription>
                    ) : null}
                  </CardHeader>
                  <CardContent>
                    <SourceStatusBadge status={video.status} />
                  </CardContent>
                </Card>
              </li>
              );
            })}
          </ul>
        )}
      </section>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Infrastructure</CardTitle>
          <CardDescription>
            Connectivity check for Neon Postgres and Qdrant Cloud.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <HealthStatus />
        </CardContent>
      </Card>
    </>
  );
}
