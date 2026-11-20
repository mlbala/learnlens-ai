/**
 * Synthetic practice fixtures — not real YouTube content.
 * Marked fixture_data throughout.
 */

import type {
  LearnerProgress,
  PresentationLanguage,
  StudyDeck,
} from "@/lib/practice/types";

export const PRACTICE_DISCLAIMER =
  "Practice counts only — no learning-efficacy claim without evaluation.";

const SEGMENT_A = "00000000-0000-4000-8000-0000000000a1";
const SEGMENT_B = "00000000-0000-4000-8000-0000000000a2";

export const FIXTURE_PRACTICE_DECK: StudyDeck = {
  id: "deck-fixture-01",
  video_id: "video-fixture-01",
  title: "Fixture practice deck (synthetic)",
  presentation_language: "en",
  origin: "fixture_data",
  fixture_data: true,
  disclaimer: PRACTICE_DISCLAIMER,
  concepts: [
    {
      id: "concept-fixture-listen",
      canonical_name: "Active listening",
      description: "Fixture concept: attend and reflect before responding.",
      evidence_segment_ids: [SEGMENT_A],
    },
    {
      id: "concept-fixture-clarify",
      canonical_name: "Clarifying questions",
      description: "Fixture concept: ask before coding.",
      evidence_segment_ids: [SEGMENT_B],
    },
  ],
  concept_edges: [
    {
      id: "edge-fixture-01",
      src_concept_id: "concept-fixture-listen",
      dst_concept_id: "concept-fixture-clarify",
      relation: "prerequisite",
    },
  ],
  items: [
    {
      id: "item-fixture-flash-01",
      deck_id: "deck-fixture-01",
      item_kind: "flashcard",
      ordinal: 0,
      prompt: "What should you do before coding?",
      answer: "Clarify requirements.",
      explanation: "Ask clarifying questions first.",
      explanation_origin: "source_supported",
      choices: [],
      correct_choice_index: null,
      evidence_segment_ids: [SEGMENT_A],
      evidence: [
        {
          segment_id: SEGMENT_A,
          snippet: "Fixture transcript: clarify requirements before coding.",
          start_ms: 12_000,
          end_ms: 18_000,
          youtube_url: null,
          timing_verified: true,
        },
      ],
      presentation: {
        en: {
          prompt: "What should you do before coding?",
          answer: "Clarify requirements.",
          explanation: "Ask clarifying questions first.",
        },
        ta: {
          prompt: "கோடிங் செய்வதற்கு முன் என்ன செய்ய வேண்டும்?",
          answer: "தேவைகளை தெளிவுபடுத்துங்கள்.",
          explanation: "முதலில் தெளிவுபடுத்தும் கேள்விகளை கேளுங்கள்.",
        },
      },
      concept_id: "concept-fixture-clarify",
      fixture_data: true,
    },
    {
      id: "item-fixture-quiz-01",
      deck_id: "deck-fixture-01",
      item_kind: "quiz",
      ordinal: 1,
      prompt: "Which action is recommended first?",
      answer: "Ask clarifying questions.",
      explanation:
        "Like checking a recipe before cooking — an AI illustration.",
      explanation_origin: "ai_generated_illustration",
      choices: [
        "Ask clarifying questions.",
        "Ship immediately.",
        "Ignore the transcript.",
        "Invent timestamps.",
      ],
      correct_choice_index: 0,
      evidence_segment_ids: [SEGMENT_B],
      evidence: [
        {
          segment_id: SEGMENT_B,
          snippet: "Fixture transcript: ask clarifying questions first.",
          start_ms: 24_000,
          end_ms: 30_000,
          youtube_url: null,
          timing_verified: true,
        },
      ],
      presentation: {
        en: {
          prompt: "Which action is recommended first?",
          answer: "Ask clarifying questions.",
          explanation:
            "Like checking a recipe before cooking — an AI illustration.",
        },
        ta: {
          prompt: "முதலில் பரிந்துரைக்கப்படும் செயல் எது?",
          answer: "தெளிவுபடுத்தும் கேள்விகளை கேளுங்கள்.",
          explanation: "AI விளக்க உதாரணம் — சமையல் குறிப்பைப் பார்த்து சமைப்பது போல.",
        },
      },
      concept_id: "concept-fixture-clarify",
      fixture_data: true,
    },
  ],
};

export const FIXTURE_PROGRESS: LearnerProgress = {
  id: "progress-fixture-01",
  video_id: "video-fixture-01",
  items_seen: 0,
  items_correct: 0,
  reviews_completed: 0,
  disclaimer: PRACTICE_DISCLAIMER,
};

export function presentItemText(
  item: StudyDeck["items"][number],
  lang: PresentationLanguage,
  field: "prompt" | "answer" | "explanation",
): string {
  const overlay = item.presentation?.[lang]?.[field];
  if (overlay && overlay.trim()) return overlay;
  return item[field];
}
