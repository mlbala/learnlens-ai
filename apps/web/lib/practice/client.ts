/**
 * Practice client — fixture mode by default (no paid API calls).
 * Set NEXT_PUBLIC_PRACTICE_MODE=api for authenticated live API.
 */

import {
  FIXTURE_PRACTICE_DECK,
  FIXTURE_PROGRESS,
} from "@/lib/practice/fixtures";
import type {
  LearnerProgress,
  PresentationLanguage,
  QuizAttemptResult,
  StudyDeck,
} from "@/lib/practice/types";

export type PracticeMode = "fixture" | "api";

export function practiceMode(): PracticeMode {
  const raw = (process.env.NEXT_PUBLIC_PRACTICE_MODE || "fixture").toLowerCase();
  return raw === "api" ? "api" : "fixture";
}

export async function loadPracticeDeck(): Promise<StudyDeck> {
  if (practiceMode() === "fixture") {
    return structuredClone(FIXTURE_PRACTICE_DECK);
  }
  const res = await fetch("/api/v1/tutor/decks", { credentials: "include" });
  if (!res.ok) {
    throw new Error(`Failed to load practice decks (${res.status})`);
  }
  const body = (await res.json()) as { items?: StudyDeck[] };
  const first = body.items?.[0];
  if (!first) {
    return structuredClone(FIXTURE_PRACTICE_DECK);
  }
  const detail = await fetch(`/api/v1/tutor/decks/${first.id}`, {
    credentials: "include",
  });
  if (!detail.ok) {
    throw new Error(`Failed to load deck (${detail.status})`);
  }
  return (await detail.json()) as StudyDeck;
}

export async function loadProgress(): Promise<LearnerProgress[]> {
  if (practiceMode() === "fixture") {
    return [structuredClone(FIXTURE_PROGRESS)];
  }
  const res = await fetch("/api/v1/tutor/progress", { credentials: "include" });
  if (!res.ok) {
    throw new Error(`Failed to load progress (${res.status})`);
  }
  const body = (await res.json()) as { items: LearnerProgress[] };
  return body.items;
}

export async function submitFixtureAttempt(
  deck: StudyDeck,
  itemId: string,
  selectedChoiceIndex: number | null,
): Promise<QuizAttemptResult> {
  const item = deck.items.find((i) => i.id === itemId);
  if (!item) {
    throw new Error("Item not found");
  }
  const isCorrect =
    item.item_kind === "quiz"
      ? selectedChoiceIndex === item.correct_choice_index
      : true;
  return {
    id: `attempt-fixture-${itemId}`,
    is_correct: isCorrect,
    evidence_resolved: item.evidence.length > 0,
    evidence: item.evidence,
    explanation: item.explanation,
    explanation_origin: item.explanation_origin,
    correct_choice_index: item.correct_choice_index,
  };
}

export function defaultLanguage(deck: StudyDeck): PresentationLanguage {
  return deck.presentation_language === "ta" ? "ta" : "en";
}
