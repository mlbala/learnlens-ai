import { Badge } from "@/components/ui/badge";
import {
  asTutorAnswer,
  hostLabel,
  parseTutorAnswer,
  type AnswerSection,
  type AnswerSource,
  type TutorAnswer,
} from "@/lib/lesson/answer";

const KIND_LABEL = {
  paper: "Paper",
  official: "Official docs",
  other: "Source",
} as const;

export function AnswerView({
  content,
  structured,
}: {
  content: string;
  structured?: TutorAnswer | null;
}) {
  const answer = asTutorAnswer(structured) ?? parseTutorAnswer(content);
  if (!answer || (answer.lesson.length === 0 && answer.external.length === 0)) {
    return <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">{content}</p>;
  }

  return (
    <div className="space-y-3">
      {answer.lesson.length > 0 ? (
        <AnswerBlock label="From the lesson" sections={answer.lesson} />
      ) : null}
      {answer.external.length > 0 ? (
        <AnswerBlock label="From papers and official docs" sections={answer.external} />
      ) : null}
      {answer.sources.length > 0 ? <SourceList sources={answer.sources} /> : null}
    </div>
  );
}

function AnswerBlock({ label, sections }: { label: string; sections: AnswerSection[] }) {
  return (
    <section className="overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface">
      <header className="border-b border-border bg-surface-muted px-4 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      </header>
      <div className="space-y-4 px-4 py-3">
        {sections.map((section) => (
          <div key={section.heading} className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">{section.heading}</h3>
            <p className="text-sm leading-6 text-foreground">{section.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function SourceList({ sources }: { sources: AnswerSource[] }) {
  return (
    <section className="rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sources</p>
      <ol className="mt-2 space-y-2">
        {sources.map((source, index) => (
          <li key={source.url} className="flex items-start gap-2">
            <span className="mt-0.5 w-4 shrink-0 text-xs tabular-nums text-muted-foreground">{index + 1}</span>
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={source.kind === "other" ? "outline" : "info"}>{KIND_LABEL[source.kind]}</Badge>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-primary underline-offset-2 hover:underline"
                >
                  {source.title}
                </a>
              </div>
              <p className="truncate text-xs text-muted-foreground">{hostLabel(source.url)}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
