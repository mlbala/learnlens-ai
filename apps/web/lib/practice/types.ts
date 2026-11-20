/**
 * Practice / tutor contracts (phase 18).
 * Aligned with packages/contracts and apps/api tutor schemas.
 */

export type PresentationLanguage = "en" | "ta";

export type ExplanationOrigin =
  | "source_supported"
  | "ai_generated_illustration"
  | string;

export type TutorEvidence = {
  segment_id: string;
  snippet: string;
  start_ms: number | null;
  end_ms: number | null;
  youtube_url: string | null;
  timing_verified: boolean;
};

export type StudyItem = {
  id: string;
  deck_id: string;
  item_kind: "flashcard" | "quiz" | string;
  ordinal: number;
  prompt: string;
  answer: string;
  explanation: string;
  explanation_origin: ExplanationOrigin;
  choices: string[];
  correct_choice_index: number | null;
  evidence_segment_ids: string[];
  evidence: TutorEvidence[];
  presentation: Record<string, { prompt?: string; answer?: string; explanation?: string }>;
  concept_id: string | null;
  fixture_data?: boolean;
};

export type ConceptNode = {
  id: string;
  canonical_name: string;
  description: string;
  evidence_segment_ids: string[];
};

export type ConceptEdge = {
  id: string;
  src_concept_id: string;
  dst_concept_id: string;
  relation: string;
};

export type StudyDeck = {
  id: string;
  video_id: string;
  title: string;
  presentation_language: PresentationLanguage | string;
  origin: string;
  items: StudyItem[];
  concepts: ConceptNode[];
  concept_edges: ConceptEdge[];
  disclaimer: string;
  fixture_data?: boolean;
};

export type LearnerProgress = {
  id: string;
  video_id: string | null;
  items_seen: number;
  items_correct: number;
  reviews_completed: number;
  disclaimer: string;
};

export type QuizAttemptResult = {
  id: string;
  is_correct: boolean;
  evidence_resolved: boolean;
  evidence: TutorEvidence[];
  explanation: string;
  explanation_origin: ExplanationOrigin;
  correct_choice_index: number | null;
};
