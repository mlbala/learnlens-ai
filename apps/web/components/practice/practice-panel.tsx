"use client";

import { useEffect, useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/patterns/page-header";
import {
  defaultLanguage,
  loadPracticeDeck,
  loadProgress,
  practiceMode,
  submitFixtureAttempt,
} from "@/lib/practice/client";
import { presentItemText } from "@/lib/practice/fixtures";
import type {
  LearnerProgress,
  PresentationLanguage,
  QuizAttemptResult,
  StudyDeck,
  StudyItem,
} from "@/lib/practice/types";
import { cn } from "@/lib/utils";

function OriginBadge({ origin }: { origin: string }) {
  if (origin === "ai_generated_illustration") {
    return <Badge variant="warning">AI illustration</Badge>;
  }
  if (origin === "source_supported") {
    return <Badge variant="success">Source-backed</Badge>;
  }
  return <Badge variant="secondary">{origin}</Badge>;
}

function EvidenceList({ item }: { item: StudyItem }) {
  if (!item.evidence.length) {
    return (
      <p className="text-xs text-muted-foreground">
        No verified source evidence for this item.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Source evidence">
      {item.evidence.map((ev) => (
        <li
          key={ev.segment_id}
          className="rounded-[var(--radius-control)] border border-border bg-surface-muted/60 px-2.5 py-2"
          data-testid={`practice-evidence-${ev.segment_id}`}
        >
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Badge variant={ev.timing_verified ? "info" : "secondary"}>
              {ev.timing_verified && ev.start_ms != null
                ? `${Math.floor(ev.start_ms / 1000)}s`
                : "Untimed"}
            </Badge>
            <span className="text-xs text-muted-foreground">Source evidence</span>
          </div>
          <p className="text-xs leading-relaxed text-foreground">{ev.snippet}</p>
        </li>
      ))}
    </ul>
  );
}

export function PracticePanel() {
  const [deck, setDeck] = useState<StudyDeck | null>(null);
  const [progress, setProgress] = useState<LearnerProgress[]>([]);
  const [lang, setLang] = useState<PresentationLanguage>("en");
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<QuizAttemptResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;
    startTransition(async () => {
      try {
        const [d, p] = await Promise.all([loadPracticeDeck(), loadProgress()]);
        if (cancelled) return;
        setDeck(d);
        setProgress(p);
        setLang(defaultLanguage(d));
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load practice");
        }
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const item = deck?.items[index] ?? null;

  function onSelectChoice(choiceIndex: number) {
    setSelected(choiceIndex);
    setRevealed(false);
    setResult(null);
  }

  function onCheck() {
    if (!deck || !item) return;
    startTransition(async () => {
      const attempt = await submitFixtureAttempt(deck, item.id, selected);
      setResult(attempt);
      setRevealed(true);
      setProgress((prev) => {
        const row = prev[0];
        if (!row) return prev;
        return [
          {
            ...row,
            items_seen: row.items_seen + 1,
            items_correct: row.items_correct + (attempt.is_correct ? 1 : 0),
          },
        ];
      });
    });
  }

  function onNext() {
    if (!deck) return;
    setIndex((i) => Math.min(i + 1, deck.items.length - 1));
    setSelected(null);
    setRevealed(false);
    setResult(null);
  }

  function onPrev() {
    setIndex((i) => Math.max(i - 1, 0));
    setSelected(null);
    setRevealed(false);
    setResult(null);
  }

  if (error) {
    return (
      <div className="rounded-[var(--radius-card)] border border-danger/40 bg-danger/5 p-4 text-sm text-danger">
        {error}
      </div>
    );
  }

  if (!deck || !item) {
    return (
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {pending ? "Loading practice…" : "No practice items available."}
      </p>
    );
  }

  const prompt = presentItemText(item, lang, "prompt");
  const answer = presentItemText(item, lang, "answer");
  const explanation = presentItemText(item, lang, "explanation");
  const prog = progress[0];

  return (
    <div className="mx-auto w-full max-w-xl" data-testid="practice-panel">
      <PageHeader
        title="Practice"
        description="Source-grounded flashcards and quizzes. AI illustrations are labeled. Counts are practice activity only."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={lang === "en" ? "default" : "outline"}
              onClick={() => setLang("en")}
              aria-pressed={lang === "en"}
            >
              English
            </Button>
            <Button
              type="button"
              size="sm"
              variant={lang === "ta" ? "default" : "outline"}
              onClick={() => setLang("ta")}
              aria-pressed={lang === "ta"}
            >
              தமிழ்
            </Button>
          </div>
        }
      />

      <p className="mb-4 text-xs text-muted-foreground">
        Mode: {practiceMode()}
        {deck.fixture_data ? " · fixture data" : null}
      </p>

      {prog ? (
        <p className="mb-6 text-sm text-muted-foreground" data-testid="practice-progress">
          Seen {prog.items_seen} · Correct {prog.items_correct}
          <span className="mt-1 block text-xs">{prog.disclaimer}</span>
        </p>
      ) : null}

      <section
        className="rounded-[var(--radius-panel)] border border-border bg-surface p-4 shadow-[var(--shadow-sm)] sm:p-6"
        aria-labelledby="practice-item-title"
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">
            {item.item_kind === "quiz" ? "Quiz" : "Flashcard"}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {index + 1} of {deck.items.length}
          </span>
          <OriginBadge origin={item.explanation_origin} />
        </div>

        <h2
          id="practice-item-title"
          className="text-lg font-semibold leading-snug text-foreground sm:text-xl"
        >
          {prompt}
        </h2>

        {item.item_kind === "quiz" ? (
          <ul className="mt-4 flex flex-col gap-2" role="listbox" aria-label="Choices">
            {item.choices.map((choice, choiceIndex) => {
              const isSelected = selected === choiceIndex;
              const showCorrect =
                revealed && choiceIndex === item.correct_choice_index;
              const showWrong =
                revealed && isSelected && choiceIndex !== item.correct_choice_index;
              return (
                <li key={`${item.id}-${choiceIndex}`}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    className={cn(
                      "min-h-11 w-full rounded-[var(--radius-control)] border px-3 py-2.5 text-left text-sm transition-colors",
                      isSelected
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border bg-surface-muted/40 text-foreground hover:bg-surface-muted",
                      showCorrect && "border-success bg-success/10",
                      showWrong && "border-danger bg-danger/10",
                    )}
                    onClick={() => onSelectChoice(choiceIndex)}
                    disabled={revealed}
                  >
                    {choice}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="mt-4">
            {!revealed ? (
              <Button type="button" onClick={() => setRevealed(true)}>
                Reveal answer
              </Button>
            ) : (
              <p className="text-sm font-medium text-foreground">{answer}</p>
            )}
          </div>
        )}

        {item.item_kind === "quiz" && !revealed ? (
          <div className="mt-4">
            <Button
              type="button"
              onClick={onCheck}
              disabled={selected == null || pending}
            >
              Check answer
            </Button>
          </div>
        ) : null}

        {revealed ? (
          <div className="mt-5 space-y-3 border-t border-border pt-4">
            {result ? (
              <p
                className={cn(
                  "text-sm font-medium",
                  result.is_correct ? "text-success" : "text-danger",
                )}
                data-testid="practice-result"
              >
                {result.is_correct ? "Correct" : "Not quite"}
                {result.evidence_resolved ? " · evidence resolved" : " · evidence missing"}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <OriginBadge origin={item.explanation_origin} />
              <span className="text-sm text-foreground">{explanation}</span>
            </div>
            <EvidenceList item={item} />
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={onPrev} disabled={index === 0}>
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onNext}
            disabled={index >= deck.items.length - 1}
          >
            Next
          </Button>
        </div>
      </section>

      {deck.concepts.length > 0 ? (
        <section className="mt-8" aria-labelledby="concept-graph-title">
          <h3
            id="concept-graph-title"
            className="mb-2 text-sm font-semibold text-foreground"
          >
            Concept prerequisites
          </h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            {deck.concept_edges.map((edge) => {
              const src = deck.concepts.find((c) => c.id === edge.src_concept_id);
              const dst = deck.concepts.find((c) => c.id === edge.dst_concept_id);
              if (!src || !dst) return null;
              return (
                <li key={edge.id}>
                  {src.canonical_name} → {dst.canonical_name}{" "}
                  <span className="text-xs">({edge.relation})</span>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
