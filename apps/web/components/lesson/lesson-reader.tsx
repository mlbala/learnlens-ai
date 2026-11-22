"use client";

import { useCallback, useState } from "react";

import { ChapterTimeline } from "@/components/lesson/chapter-timeline";
import { ChatPanel } from "@/components/lesson/chat-panel";
import { SummaryPanel } from "@/components/lesson/summary-panel";
import { TranscriptPanel } from "@/components/lesson/transcript-panel";
import { YoutubePlayer, type SeekRequest } from "@/components/lesson/youtube-player";
import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { SourceStatusBadge } from "@/components/patterns/source-status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useLessonBundle } from "@/lib/lesson/query";
import type { VideoRecord } from "@/lib/library/types";
import { cn } from "@/lib/utils";

type LessonReaderProps = {
  video: VideoRecord;
  className?: string;
};

export function LessonReader({ video, className }: LessonReaderProps) {
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null);
  const [draftQuestion, setDraftQuestion] = useState<string | null>(null);

  const bundleQuery = useLessonBundle(video.id, {
    enabled: video.transcript_access,
  });

  const requestSeek = useCallback((seconds: number) => {
    setSeekRequest({ seconds, token: Date.now() });
  }, []);

  const askAbout = useCallback((prompt: string) => {
    setDraftQuestion(prompt);
    document.getElementById("ask-ai")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  if (!video.transcript_access) {
    return null;
  }

  if (bundleQuery.isLoading) {
    return <PageSkeleton className={className} />;
  }

  if (bundleQuery.isError) {
    return (
      <ErrorState
        title="Lesson content unavailable"
        message={
          bundleQuery.error instanceof Error
            ? bundleQuery.error.message
            : "Could not load chapters or notes."
        }
        action={
          <Button type="button" variant="outline" onClick={() => void bundleQuery.refetch()}>
            Retry
          </Button>
        }
        className={className}
      />
    );
  }

  const bundle = bundleQuery.data;
  const chapters = bundle?.chapters ?? [];
  const summaries = bundle?.summaries ?? [];
  const snippets = bundle?.snippets ?? [];
  const starters = bundle?.starter_questions ?? [];
  const fixturePlayer = Boolean(video.fixture_data);

  return (
    <div className={cn("space-y-6", className)}>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="order-1 lg:col-span-7">
          <YoutubePlayer
            youtubeVideoId={video.youtube_video_id}
            title={video.title}
            seekRequest={seekRequest}
            fixturePlaceholder={fixturePlayer}
          />
        </div>

        <aside className="order-2 space-y-4 lg:sticky lg:top-4 lg:col-span-5 lg:col-start-8 lg:row-span-3 lg:row-start-1 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <section aria-labelledby="lesson-notes-heading" className="space-y-3">
            <h2 id="lesson-notes-heading" className="text-lg font-semibold text-foreground">
              Study notes
            </h2>
            <SummaryPanel summaries={summaries} onAskAbout={askAbout} />
          </section>
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
                {fixturePlayer
                  ? "Fixture data only."
                  : "Gemini built this lesson from the public YouTube video."}
              </p>
            </CardContent>
          </Card>
        </aside>

        <section id="ask-ai" aria-labelledby="ask-ai-heading" className="order-3 scroll-mt-20 space-y-3 lg:col-span-7">
          <h2 id="ask-ai-heading" className="text-lg font-semibold text-foreground">
            Ask AI
          </h2>
          <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-4">
            <ChatPanel
              videoId={video.id}
              youtubeVideoId={video.youtube_video_id}
              transcriptAccess={video.transcript_access}
              starterQuestions={starters}
              draftQuestion={draftQuestion}
              onDraftConsumed={() => setDraftQuestion(null)}
              onSeek={requestSeek}
            />
          </div>
        </section>

        <div className="order-4 space-y-6 lg:col-span-7">
          <section aria-labelledby="lesson-chapters-heading" className="space-y-3">
            <h2 id="lesson-chapters-heading" className="text-lg font-semibold text-foreground">
              Chapters
            </h2>
            <ChapterTimeline chapters={chapters} onSeek={requestSeek} />
          </section>
          <section aria-labelledby="lesson-transcript-heading" className="space-y-3">
            <h2 id="lesson-transcript-heading" className="text-lg font-semibold text-foreground">
              Transcript snippets
            </h2>
            <TranscriptPanel snippets={snippets} onSeek={requestSeek} />
          </section>
        </div>
      </div>

      {chapters.length === 0 && summaries.length === 0 && snippets.length === 0 ? (
        <EmptyState
          title="Lesson content not ready"
          description="This video has transcript access, but chapters and notes are empty. Summarization may still be pending."
        />
      ) : null}
    </div>
  );
}
