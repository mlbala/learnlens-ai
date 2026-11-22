"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/patterns/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { noteParagraphs, recoverLessonFields } from "@/lib/lesson/notes";
import type { LessonSummary } from "@/lib/lesson/types";
import { cn } from "@/lib/utils";

type SummaryPanelProps = {
  summaries: LessonSummary[];
  onAskAbout?: (prompt: string) => void;
  className?: string;
};

function pickKind(items: LessonSummary[], kind: string): LessonSummary | undefined {
  return items.find((s) => s.summary_kind === kind && s.status === "ready");
}

export function SummaryPanel({ summaries, onAskAbout, className }: SummaryPanelProps) {
  const short = useMemo(() => pickKind(summaries, "short"), [summaries]);
  const detailed = useMemo(
    () => pickKind(summaries, "detailed") ?? pickKind(summaries, "technical"),
    [summaries],
  );
  const [copied, setCopied] = useState(false);

  if (!short && !detailed) {
    return (
      <EmptyState
        title="No study notes yet"
        description="Notes appear here after Gemini finishes the lesson."
        className={className}
      />
    );
  }

  const defaultTab = short ? "concise" : "detailed";

  async function copyNotes(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className={cn("space-y-3", className)}>
      <Tabs defaultValue={defaultTab}>
        <TabsList aria-label="Notes detail" className="justify-start">
          <TabsTrigger value="concise" disabled={!short}>
            Concise
          </TabsTrigger>
          <TabsTrigger value="detailed" disabled={!detailed}>
            Detailed
          </TabsTrigger>
        </TabsList>
        {short ? (
          <TabsContent value="concise">
            <NotesBody
              summary={short}
              onCopy={() => void copyNotes(formatNotes(short))}
              onAskAbout={onAskAbout}
              copied={copied}
            />
          </TabsContent>
        ) : null}
        {detailed ? (
          <TabsContent value="detailed">
            <NotesBody
              summary={detailed}
              onCopy={() => void copyNotes(formatNotes(detailed))}
              onAskAbout={onAskAbout}
              copied={copied}
            />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
}

function NotesBody({
  summary,
  onCopy,
  onAskAbout,
  copied,
}: {
  summary: LessonSummary;
  onCopy: () => void;
  onAskAbout?: (prompt: string) => void;
  copied: boolean;
}) {
  const notes = recoverLessonFields({ summary: summary.summary, key_points: summary.key_points });
  const paragraphs = noteParagraphs(notes.summary);
  const points = notes.keyPoints;
  return (
    <article className="space-y-4 rounded-[var(--radius-card)] border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onCopy}>
          {copied ? "Copied" : "Copy notes"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => onAskAbout?.(`Explain: ${points[0] ?? notes.summary.slice(0, 80)}`)}
          disabled={!onAskAbout}
        >
          Ask about this
        </Button>
      </div>
      <section className="space-y-2" aria-label="Overview">
        <h3 className="text-sm font-semibold text-foreground">Overview</h3>
        {paragraphs.map((paragraph) => (
          <p key={paragraph} className="text-sm leading-6 text-foreground">
            {paragraph}
          </p>
        ))}
      </section>
      {points.length > 0 ? (
        <section className="space-y-2" aria-label="Key points">
          <h3 className="text-sm font-semibold text-foreground">Key points</h3>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-foreground">
            {points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {summary.claims.length > 0 ? (
        <section aria-label="Source-backed claims" className="space-y-2">
          <h3 className="text-sm font-semibold text-foreground">Source-backed claims</h3>
          {summary.claims.map((claim) => (
            <div key={claim.text} className="rounded-[var(--radius-control)] bg-surface-muted px-3 py-2">
              <div className="mb-1 flex flex-wrap gap-2">
                <Badge variant="success">source-backed</Badge>
              </div>
              <p className="text-sm text-foreground">{claim.text}</p>
            </div>
          ))}
        </section>
      ) : null}
      {summary.examples.length > 0 ? (
        <section aria-label="AI illustrations" className="space-y-2">
          <h3 className="text-sm font-semibold text-foreground">AI illustrations (extras)</h3>
          {summary.examples.map((ex) => (
            <div
              key={ex.text}
              className="rounded-[var(--radius-control)] border border-dashed border-border px-3 py-2"
            >
              <div className="mb-1 flex flex-wrap gap-2">
                <Badge variant="warning">AI-created analogy</Badge>
                <span className="text-xs text-muted-foreground">Not source evidence</span>
              </div>
              <p className="text-sm text-muted-foreground">{ex.text}</p>
            </div>
          ))}
        </section>
      ) : null}
      {summary.fixture_data ? (
        <p className="text-xs text-muted-foreground">Fixture data only — synthetic notes, not YouTube captions.</p>
      ) : null}
    </article>
  );
}

function formatNotes(summary: LessonSummary): string {
  const notes = recoverLessonFields({ summary: summary.summary, key_points: summary.key_points });
  const lines = ["Overview", ...noteParagraphs(notes.summary), "", "Key points", ...notes.keyPoints.map((point) => `• ${point}`)];
  return lines.join("\n");
}
