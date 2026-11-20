"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/patterns/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatCourseNotesMarkdown } from "@/lib/library/course-summary";
import type { PlaylistCourseSummary } from "@/lib/library/types";
import { playlistCoverageLabel } from "@/lib/status";

type CourseOverviewProps = {
  summary: PlaylistCourseSummary | null | undefined;
  loading?: boolean;
  onSynthesize?: () => void;
  synthesizing?: boolean;
};

export function CourseOverview({
  summary,
  loading,
  onSynthesize,
  synthesizing,
}: CourseOverviewProps) {
  const [copied, setCopied] = useState(false);
  const markdown = useMemo(
    () => (summary ? formatCourseNotesMarkdown(summary) : ""),
    [summary],
  );

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Course overview</CardTitle>
          <CardDescription>Loading synthesis…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!summary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Course overview</CardTitle>
          <CardDescription>
            Combine ready per-video notes into modules, a learning map, and takeaways. Missing
            lessons stay excluded.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No course notes yet"
            description="Run synthesis after at least one playlist lesson has a permitted transcript."
            action={
              onSynthesize ? (
                <Button type="button" onClick={onSynthesize} disabled={synthesizing}>
                  {synthesizing ? "Synthesizing…" : "Synthesize course notes"}
                </Button>
              ) : undefined
            }
          />
        </CardContent>
      </Card>
    );
  }

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const isPartial = summary.coverage_label !== "complete";

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-base">Course overview</CardTitle>
            <Badge variant={isPartial ? "secondary" : "default"}>
              {isPartial ? "Partial" : "Complete"}
            </Badge>
            {summary.fixture_data ? <Badge variant="outline">Fixture data</Badge> : null}
          </div>
          <CardDescription>
            {playlistCoverageLabel(summary.included_count, summary.total_count)}
            {summary.caveat ? ` · ${summary.caveat}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="leading-relaxed text-foreground">{summary.overview}</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void copyMarkdown()}>
              {copied ? "Copied" : "Copy Markdown notes"}
            </Button>
            {onSynthesize ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={onSynthesize}
                disabled={synthesizing}
              >
                {synthesizing ? "Refreshing…" : "Refresh synthesis"}
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {summary.topic_modules.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Topic modules</CardTitle>
            <CardDescription>Grouped from included ready lessons only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.topic_modules.map((mod) => (
              <div key={mod.title} className="space-y-1 border-b border-border/60 pb-3 last:border-0">
                <p className="font-medium">{mod.title}</p>
                <p className="text-sm text-muted-foreground">{mod.summary}</p>
                <p className="text-xs text-muted-foreground">
                  Sources: {mod.video_ids.length} video(s)
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {summary.learning_map.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Learning map</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-1 pl-5 text-sm">
              {[...summary.learning_map]
                .sort((a, b) => a.order - b.order)
                .map((node) => (
                  <li key={`${node.order}-${node.label}`}>{node.label}</li>
                ))}
            </ol>
          </CardContent>
        </Card>
      ) : null}

      {summary.cross_video_concepts.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cross-video concepts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.cross_video_concepts.map((concept) => (
              <div key={concept.name} className="space-y-1">
                <p className="font-medium">{concept.name}</p>
                <p className="text-sm text-muted-foreground">{concept.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {summary.key_takeaways.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Key takeaways</CardTitle>
            <CardDescription>Each takeaway maps to included video evidence.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-2 pl-5 text-sm">
              {summary.key_takeaways.map((t) => (
                <li key={t.text}>
                  {t.text}
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    Evidence segments: {t.evidence_segment_ids.length || 0} · Videos:{" "}
                    {t.source_video_ids.length || 0}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {summary.excluded_video_ids.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Excluded lessons</CardTitle>
            <CardDescription>
              Not synthesized — no invented coverage for missing or unavailable items.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {summary.excluded_count} excluded of {summary.total_count} total.
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
