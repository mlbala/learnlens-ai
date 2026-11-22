import { BookOpen, Globe, Link2, SearchCheck as SearchCheckIcon } from "lucide-react";

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
        <AnswerBlock label="From the lesson" sections={answer.lesson} tone="lesson" />
      ) : null}
      {answer.external.length > 0 ? (
        <AnswerBlock label="From papers and official docs" sections={answer.external} tone="external" />
      ) : null}
      {answer.sources.length > 0 ? <SourceList sources={answer.sources} /> : null}
      <SearchCheck answer={answer} />
    </div>
  );
}

function SearchCheck({ answer }: { answer: TutorAnswer }) {
  const plan = answer.web_search;
  const searched =
    plan?.accepted === true || (answer.outside_lane_empty === true && plan?.accepted !== false);
  if (!plan && !searched) return null;
  return (
    <section className="space-y-2 rounded-[var(--radius-card)] border border-dashed border-border bg-surface-muted/40 px-4 py-3">
      {plan ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <SearchCheckIcon className="h-3.5 w-3.5" aria-hidden />
              Search check
            </p>
            <Badge variant={plan.accepted ? "success" : "warning"}>Score {plan.score}</Badge>
          </div>
          {plan.keywords.length > 0 ? (
            <ul className="flex flex-wrap gap-1.5" aria-label="Search words">
              {plan.keywords.map((keyword) => (
                <li key={keyword}>
                  <Badge variant="outline">{keyword}</Badge>
                </li>
              ))}
            </ul>
          ) : null}
          {plan.queries[0] ? (
            <p className="text-xs leading-5 text-muted-foreground">Query: {plan.queries[0]}</p>
          ) : null}
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">
        {searched
          ? "Searched academic papers and official documents."
          : plan?.note || "Search words were not strong enough, so this answer stays with the lesson."}
      </p>
    </section>
  );
}

function AnswerBlock({
  label,
  sections,
  tone,
}: {
  label: string;
  sections: AnswerSection[];
  tone: "lesson" | "external";
}) {
  const Icon = tone === "lesson" ? BookOpen : Globe;
  return (
    <section className="overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface shadow-[var(--shadow-sm)]">
      <header
        className={
          tone === "lesson"
            ? "flex items-center gap-2 border-b border-border bg-primary/5 px-4 py-2 text-primary"
            : "flex items-center gap-2 border-b border-border bg-accent/10 px-4 py-2 text-accent"
        }
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
        <p className="text-xs font-semibold uppercase tracking-wide">{label}</p>
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
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Link2 className="h-3.5 w-3.5" aria-hidden />
        Sources
      </p>
      <ol className="mt-2 space-y-2">
        {sources.map((source, index) => (
          <li key={source.url} className="flex items-start gap-2">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-muted text-[11px] font-medium tabular-nums text-muted-foreground">
              {index + 1}
            </span>
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
