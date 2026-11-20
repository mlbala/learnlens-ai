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
  const [mobileTab, setMobileTab] = useState("notes");

  const bundleQuery = useLessonBundle(video.id, {
    enabled: video.transcript_access,
  });

  const requestSeek = useCallback((seconds: number) => {
    setSeekRequest({ seconds, token: Date.now() });
  }, []);

  const askAbout = useCallback((prompt: string) => {
    setDraftQuestion(prompt);
    setMobileTab("chat");
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
  const showMobileChat = mobileTab === "chat";

  return (
    <div className={cn("space-y-6", className)}>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className={cn("space-y-6", showMobileChat ? "max-lg:hidden" : "", "lg:col-span-8")}>
          <YoutubePlayer
            youtubeVideoId={video.youtube_video_id}
            title={video.title}
            seekRequest={seekRequest}
            fixturePlaceholder={fixturePlayer}
          />

          <div className="hidden space-y-6 lg:block">
            <section aria-labelledby="lesson-chapters-heading" className="space-y-3">
              <h2 id="lesson-chapters-heading" className="text-lg font-semibold text-foreground">
                Chapters
              </h2>
              <ChapterTimeline chapters={chapters} onSeek={requestSeek} />
            </section>

            <section aria-labelledby="lesson-notes-heading" className="space-y-3">
              <h2 id="lesson-notes-heading" className="text-lg font-semibold text-foreground">
                Study notes
              </h2>
              <SummaryPanel summaries={summaries} onAskAbout={askAbout} />
            </section>

            <section aria-labelledby="lesson-transcript-heading" className="space-y-3">
              <h2 id="lesson-transcript-heading" className="text-lg font-semibold text-foreground">
                Transcript snippets
              </h2>
              <TranscriptPanel snippets={snippets} onSeek={requestSeek} />
            </section>
          </div>

          <div className="lg:hidden">
            <Tabs value={mobileTab} onValueChange={setMobileTab}>
              <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1">
                <TabsTrigger value="chapters">Chapters</TabsTrigger>
                <TabsTrigger value="notes">Notes</TabsTrigger>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="chat">Ask AI</TabsTrigger>
              </TabsList>
              <TabsContent value="chapters">
                <ChapterTimeline chapters={chapters} onSeek={requestSeek} />
              </TabsContent>
              <TabsContent value="notes">
                <SummaryPanel summaries={summaries} onAskAbout={askAbout} />
              </TabsContent>
              <TabsContent value="transcript">
                <TranscriptPanel snippets={snippets} onSeek={requestSeek} />
              </TabsContent>
            </Tabs>
          </div>
        </div>

        {/* Single ChatPanel instance — side panel on lg, full-width drawer on small */}
        <aside
          className={cn(
            "space-y-4 lg:col-span-4",
            showMobileChat ? "block" : "hidden lg:block",
          )}
        >
          <div className="lg:hidden">
            <Tabs value="chat" onValueChange={setMobileTab}>
              <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1">
                <TabsTrigger value="chapters">Chapters</TabsTrigger>
                <TabsTrigger value="notes">Notes</TabsTrigger>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="chat">Ask AI</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <Card className="hidden lg:block">
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
          <div className="max-h-[calc(100vh-6rem)] overflow-y-auto rounded-[var(--radius-panel)] border border-border bg-surface p-4 lg:sticky lg:top-4">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Ask AI</h2>
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
        </aside>
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
