"use client";

import { FileText, ListOrdered, ScrollText, ShieldCheck } from "lucide-react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

  const outerTrigger =
    "gap-2 rounded-none border-b-2 border-transparent px-1 pb-2.5 pt-1 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none";

  return (
    <div className={cn("space-y-6", className)}>
      <div className="grid items-start gap-6 lg:grid-cols-12">
        <section
          aria-labelledby="lesson-video-heading"
          className="min-w-0 space-y-3 lg:col-span-7 lg:col-start-1 lg:row-start-1"
        >
          <h2 id="lesson-video-heading" className="sr-only">
            Video
          </h2>
          <div className="overflow-hidden rounded-[var(--radius-panel)] border border-border bg-surface shadow-[var(--shadow-md)]">
            <YoutubePlayer
              youtubeVideoId={video.youtube_video_id}
              title={video.title}
              seekRequest={seekRequest}
              fixturePlaceholder={fixturePlayer}
            />
          </div>
        </section>

        <aside
          id="ask-ai"
          aria-labelledby="ask-ai-heading"
          className="min-w-0 scroll-mt-20 self-start lg:sticky lg:top-20 lg:col-span-5 lg:col-start-8 lg:row-span-2 lg:row-start-1"
        >
          <h2 id="ask-ai-heading" className="sr-only">
            Ask AI
          </h2>
          <ChatPanel
            videoId={video.id}
            youtubeVideoId={video.youtube_video_id}
            transcriptAccess={video.transcript_access}
            starterQuestions={starters}
            draftQuestion={draftQuestion}
            onDraftConsumed={() => setDraftQuestion(null)}
            onSeek={requestSeek}
            className="h-[38rem] lg:h-[calc(100vh-6.5rem)]"
          />
        </aside>

        <div className="min-w-0 space-y-6 lg:col-span-7 lg:col-start-1 lg:row-start-2">
          <Tabs defaultValue="notes">
            <TabsList
              aria-label="Lesson content"
              className="h-auto w-full justify-start gap-5 rounded-none border-b border-border bg-transparent p-0"
            >
              <TabsTrigger value="notes" className={outerTrigger}>
                <FileText className="h-4 w-4" aria-hidden />
                Study notes
              </TabsTrigger>
              <TabsTrigger value="chapters" className={outerTrigger}>
                <ListOrdered className="h-4 w-4" aria-hidden />
                Chapters
                {chapters.length > 0 ? (
                  <span className="rounded-full bg-surface-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">
                    {chapters.length}
                  </span>
                ) : null}
              </TabsTrigger>
              <TabsTrigger value="transcript" className={outerTrigger}>
                <ScrollText className="h-4 w-4" aria-hidden />
                Transcript
              </TabsTrigger>
            </TabsList>
            <TabsContent value="notes" className="mt-5">
              <h2 id="lesson-notes-heading" className="sr-only">
                Study notes
              </h2>
              <SummaryPanel summaries={summaries} onAskAbout={askAbout} />
            </TabsContent>
            <TabsContent value="chapters" className="mt-5">
              <h2 id="lesson-chapters-heading" className="sr-only">
                Chapters
              </h2>
              <ChapterTimeline chapters={chapters} onSeek={requestSeek} />
            </TabsContent>
            <TabsContent value="transcript" className="mt-5">
              <h2 id="lesson-transcript-heading" className="sr-only">
                Transcript
              </h2>
              <TranscriptPanel snippets={snippets} onSeek={requestSeek} />
            </TabsContent>
          </Tabs>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldCheck className="h-4 w-4 text-success" aria-hidden />
                Source quality
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Status</span>
                <SourceStatusBadge status={video.status} />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">YouTube ID</span>
                <span className="font-mono text-xs">{video.youtube_video_id}</span>
              </div>
              <p className="text-xs leading-5 text-muted-foreground">
                {fixturePlayer
                  ? "Fixture data only."
                  : "Gemini built this lesson from the public YouTube video."}
              </p>
            </CardContent>
          </Card>
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
