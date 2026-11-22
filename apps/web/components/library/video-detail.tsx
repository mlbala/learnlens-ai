"use client";

import Link from "next/link";

import { LessonReader } from "@/components/lesson/lesson-reader";
import { YoutubePlayer } from "@/components/lesson/youtube-player";
import { FixtureModeBanner } from "@/components/library/fixture-mode-banner";
import { TranscriptImportDialog } from "@/components/library/transcript-import-dialog";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageHeader } from "@/components/patterns/page-header";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { SourceStatusBadge } from "@/components/patterns/source-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { resolveLibraryMode } from "@/lib/library/client";
import { formatDuration } from "@/lib/library/coverage";
import { useVideo } from "@/lib/library/query";

type VideoDetailProps = {
  videoId: string;
};

export function VideoDetail({ videoId }: VideoDetailProps) {
  const mode = resolveLibraryMode();
  const query = useVideo(videoId);

  if (query.isLoading) return <PageSkeleton />;

  if (query.isError) {
    return (
      <ErrorState
        title="Video unavailable"
        message={query.error instanceof Error ? query.error.message : "Not found"}
        action={
          <Button type="button" variant="outline" onClick={() => void query.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  const video = query.data;
  if (!video) return null;

  const needsTranscript =
    video.status === "needs_transcript" || video.status === "metadata_only";
  const unavailable = video.status === "unavailable";

  return (
    <>
      <PageHeader
        title={video.title}
        description={`${video.channel_title ?? "Unknown channel"} · ${formatDuration(video.duration_seconds)}${video.fixture_data ? " · Fixture data" : ""}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <SourceStatusBadge status={video.status} />
            {video.transcript_access ? null : (
              <TranscriptImportDialog
                videoId={video.id}
                videoTitle={video.title}
                disabled={unavailable}
                disabledReason="Unavailable videos cannot accept transcripts."
              />
            )}
            <Button asChild variant="outline">
              <Link href="/videos">Back to videos</Link>
            </Button>
          </div>
        }
      />
      {video.fixture_data ? <FixtureModeBanner mode={mode} /> : null}

      {needsTranscript && video.fixture_data ? (
        <Alert variant="warning" className="mb-6">
          <AlertTitle>Transcript needed</AlertTitle>
          <AlertDescription>
            Metadata import does not grant caption access. Upload a permitted SRT/VTT/TXT or paste
            a transcript you have rights to process. A URL alone never yields knowledge.
          </AlertDescription>
        </Alert>
      ) : null}

      {!video.transcript_access && !needsTranscript && !unavailable ? (
        <Alert variant="warning" className="mb-6">
          <AlertTitle>Limited source</AlertTitle>
          <AlertDescription>
            Study features that require a transcript remain disabled until an attested upload
            succeeds.
          </AlertDescription>
        </Alert>
      ) : null}

      {video.transcript_access ? (
        <LessonReader video={video} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">
            <YoutubePlayer
              youtubeVideoId={video.youtube_video_id}
              title={video.title}
              fixturePlaceholder={Boolean(video.fixture_data)}
            />
            <EmptyState
              title="No transcript attached"
              description="Upload a permitted transcript to unlock the lesson reader, notes, and Ask AI. We never scrape YouTube captions."
              action={
                <TranscriptImportDialog
                  videoId={video.id}
                  videoTitle={video.title}
                  disabled={unavailable}
                  disabledReason="Unavailable videos cannot accept transcripts."
                />
              }
            />
          </div>
          <aside className="space-y-4 lg:col-span-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Source quality</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">Status</span>
                  <SourceStatusBadge status={video.status} />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">YouTube ID</span>
                  <span className="font-mono text-xs">{video.youtube_video_id}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Owner-authorized caption download is not configured in this environment.
                </p>
              </CardContent>
            </Card>
          </aside>
        </div>
      )}
    </>
  );
}
