/**
 * Lesson reader + grounded chat contracts (phase 11).
 * Aligned with packages/contracts and apps/api schemas.
 */

export type ExplanationMode = "simple" | "standard" | "technical";

export type LessonChapter = {
  id: string;
  video_id: string;
  workspace_id: string;
  source_revision: number;
  title: string;
  start_segment_id?: string | null;
  end_segment_id?: string | null;
  /** Verified start time when known; null means no precise jump. */
  start_ms?: number | null;
  topic_json?: Record<string, unknown> | null;
  fixture_data?: boolean;
};

export type SummaryClaim = {
  text: string;
  evidence_segment_ids: string[];
  provenance: string;
};

export type SummaryExample = {
  text: string;
  origin: string;
};

export type LessonSummary = {
  id: string;
  workspace_id: string;
  scope_kind: string;
  scope_id: string;
  summary_kind: string;
  revision: number;
  status: string;
  summary: string;
  key_points: string[];
  claims: SummaryClaim[];
  examples: SummaryExample[];
  evidence_segment_ids: string[];
  origin?: string | null;
  fixture_data?: boolean;
};

export type TranscriptSnippet = {
  id: string;
  ordinal: number;
  text: string;
  start_ms: number | null;
  end_ms: number | null;
  content_hash: string;
  fixture_data?: boolean;
};

export type Citation = {
  citation_id: string;
  video_id: string;
  video_title: string;
  segment_id: string;
  snippet: string;
  start_ms: number | null;
  end_ms: number | null;
  youtube_url: string | null;
  timing_verified: boolean;
};

export type QaClaim = {
  text: string;
  citation_segment_ids: string[];
};

export type QaAnalogy = {
  text: string;
  origin: string;
};

export type ChatThread = {
  id: string;
  workspace_id: string;
  scope_kind: string;
  scope_id: string | null;
  title: string | null;
  created_by: string;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  thread_id: string;
  workspace_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  explanation_mode?: ExplanationMode | string | null;
  confidence_label?: string | null;
  unsupported: boolean;
  claims: QaClaim[];
  analogies: QaAnalogy[];
  citations: Citation[];
  provider_run_id?: string | null;
  created_at: string;
  /** Streaming-ready UI hint — never invents completion. */
  stream_state?: "idle" | "pending" | "complete" | "error";
};

export type PostChatResult = {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  unsupported: boolean;
  confidence_label: string;
  explanation_mode: string;
};

export type LessonBundle = {
  chapters: LessonChapter[];
  summaries: LessonSummary[];
  snippets: TranscriptSnippet[];
  starter_questions: string[];
  fixture_data: boolean;
};

export class LessonApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId?: string;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.name = "LessonApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}
