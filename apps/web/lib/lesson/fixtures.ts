/**
 * Synthetic lesson + chat fixtures — never presented as real YouTube captions.
 */

import { FIXTURE_WORKSPACE_ID } from "@/lib/library/fixtures";
import type {
  ChatMessage,
  ChatThread,
  Citation,
  LessonBundle,
  LessonChapter,
  LessonSummary,
  PostChatResult,
  TranscriptSnippet,
} from "@/lib/lesson/types";

const WS = FIXTURE_WORKSPACE_ID;
const ACTOR = "00000000-0000-4000-8000-0000000000aa";

/** Ready fixture video used for full lesson demos. */
export const FIXTURE_LESSON_VIDEO_ID = "11111111-1111-4111-8111-111111111101";
export const FIXTURE_LESSON_YOUTUBE_ID = "vidPublic01";
export const FIXTURE_LESSON_TITLE = "Fixture lecture 1: Active listening (synthetic)";

const SEG = {
  s1: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01",
  s2: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02",
  s3: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa03",
  s4: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa04",
  /** Untimed TXT-style segment — no precise jump. */
  s5: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa05",
} as const;

export const FIXTURE_SNIPPETS: TranscriptSnippet[] = [
  {
    id: SEG.s1,
    ordinal: 0,
    text: "Fixture transcript: Active listening starts with full attention to the speaker. (synthetic)",
    start_ms: 12_000,
    end_ms: 28_000,
    content_hash: "fixture-seg-01",
    fixture_data: true,
  },
  {
    id: SEG.s2,
    ordinal: 1,
    text: "Fixture transcript: Restate requirements before offering feedback in a review. (synthetic)",
    start_ms: 95_000,
    end_ms: 118_000,
    content_hash: "fixture-seg-02",
    fixture_data: true,
  },
  {
    id: SEG.s3,
    ordinal: 2,
    text: "Fixture transcript: Clarifying questions reduce costly misunderstandings. (synthetic)",
    start_ms: 210_000,
    end_ms: 235_000,
    content_hash: "fixture-seg-03",
    fixture_data: true,
  },
  {
    id: SEG.s4,
    ordinal: 3,
    text: "Fixture transcript: Summarize agreements at the end of the conversation. (synthetic)",
    start_ms: 420_000,
    end_ms: 445_000,
    content_hash: "fixture-seg-04",
    fixture_data: true,
  },
  {
    id: SEG.s5,
    ordinal: 4,
    text: "Fixture TXT segment without timecodes — source available without exact time. (synthetic)",
    start_ms: null,
    end_ms: null,
    content_hash: "fixture-seg-05",
    fixture_data: true,
  },
];

export const FIXTURE_CHAPTERS: LessonChapter[] = [
  {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb01",
    video_id: FIXTURE_LESSON_VIDEO_ID,
    workspace_id: WS,
    source_revision: 1,
    title: "Attention and presence",
    start_segment_id: SEG.s1,
    end_segment_id: SEG.s1,
    start_ms: 12_000,
    topic_json: { fixture_data: true },
    fixture_data: true,
  },
  {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb02",
    video_id: FIXTURE_LESSON_VIDEO_ID,
    workspace_id: WS,
    source_revision: 1,
    title: "Restating requirements",
    start_segment_id: SEG.s2,
    end_segment_id: SEG.s2,
    start_ms: 95_000,
    topic_json: { fixture_data: true },
    fixture_data: true,
  },
  {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb03",
    video_id: FIXTURE_LESSON_VIDEO_ID,
    workspace_id: WS,
    source_revision: 1,
    title: "Closing the loop",
    start_segment_id: SEG.s4,
    end_segment_id: SEG.s5,
    start_ms: 420_000,
    topic_json: { fixture_data: true },
    fixture_data: true,
  },
];

const SHORT_SUMMARY: LessonSummary = {
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccc01",
  workspace_id: WS,
  scope_kind: "video",
  scope_id: FIXTURE_LESSON_VIDEO_ID,
  summary_kind: "short",
  revision: 1,
  status: "ready",
  summary:
    "Fixture short notes: Give undivided attention, restate requirements, and close with a shared summary. (synthetic)",
  key_points: [
    "Attend fully before responding",
    "Restate requirements in reviews",
    "End with an explicit agreement summary",
  ],
  claims: [
    {
      text: "Active listening starts with full attention.",
      evidence_segment_ids: [SEG.s1],
      provenance: "source_supported",
    },
  ],
  examples: [
    {
      text: "Think of a radio tuned to one station — filter noise before answering. (AI illustration)",
      origin: "ai_generated_illustration",
    },
  ],
  evidence_segment_ids: [SEG.s1, SEG.s2, SEG.s4],
  origin: "fixture",
  fixture_data: true,
};

const DETAILED_SUMMARY: LessonSummary = {
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccc02",
  workspace_id: WS,
  scope_kind: "video",
  scope_id: FIXTURE_LESSON_VIDEO_ID,
  summary_kind: "detailed",
  revision: 1,
  status: "ready",
  summary:
    "Fixture detailed notes: The lecture walks through attention, clarifying questions, and closing agreements using synthetic evidence only. Prefer source-backed claims over illustrations.",
  key_points: [
    "Attention is a prerequisite for accurate restatement",
    "Clarifying questions prevent rework",
    "Untimed transcript text must not invent jump links",
  ],
  claims: [
    {
      text: "Restate requirements before offering feedback.",
      evidence_segment_ids: [SEG.s2],
      provenance: "source_supported",
    },
    {
      text: "Clarifying questions reduce misunderstandings.",
      evidence_segment_ids: [SEG.s3],
      provenance: "source_supported",
    },
  ],
  examples: [
    {
      text: "Like a debugger stepping through assumptions before changing code. (AI illustration)",
      origin: "ai_generated_illustration",
    },
  ],
  evidence_segment_ids: [SEG.s1, SEG.s2, SEG.s3, SEG.s4, SEG.s5],
  origin: "fixture",
  fixture_data: true,
};

export const FIXTURE_SUMMARIES: LessonSummary[] = [SHORT_SUMMARY, DETAILED_SUMMARY];

export const FIXTURE_STARTER_QUESTIONS = [
  "What does active listening require first?",
  "How should I restate requirements in a review?",
  "What should I do at the end of a conversation?",
];

export function fixtureLessonBundle(videoId: string): LessonBundle | null {
  if (videoId !== FIXTURE_LESSON_VIDEO_ID) {
    return {
      chapters: [],
      summaries: [],
      snippets: [],
      starter_questions: [],
      fixture_data: true,
    };
  }
  return {
    chapters: structuredClone(FIXTURE_CHAPTERS),
    summaries: structuredClone(FIXTURE_SUMMARIES),
    snippets: structuredClone(FIXTURE_SNIPPETS),
    starter_questions: [...FIXTURE_STARTER_QUESTIONS],
    fixture_data: true,
  };
}

function timedCitation(
  id: string,
  segmentId: string,
  snippet: string,
  startMs: number,
  endMs: number,
): Citation {
  const seconds = Math.floor(startMs / 1000);
  return {
    citation_id: id,
    video_id: FIXTURE_LESSON_VIDEO_ID,
    video_title: FIXTURE_LESSON_TITLE,
    segment_id: segmentId,
    snippet,
    start_ms: startMs,
    end_ms: endMs,
    youtube_url: `https://www.youtube.com/watch?v=${FIXTURE_LESSON_YOUTUBE_ID}&t=${seconds}s`,
    timing_verified: true,
  };
}

function untimedCitation(id: string, segmentId: string, snippet: string): Citation {
  return {
    citation_id: id,
    video_id: FIXTURE_LESSON_VIDEO_ID,
    video_title: FIXTURE_LESSON_TITLE,
    segment_id: segmentId,
    snippet,
    start_ms: null,
    end_ms: null,
    youtube_url: `https://www.youtube.com/watch?v=${FIXTURE_LESSON_YOUTUBE_ID}`,
    timing_verified: false,
  };
}

type ThreadStore = {
  thread: ChatThread;
  messages: ChatMessage[];
};

/** Mutable in-memory chat store for fixture demos. */
const threadByVideo = new Map<string, ThreadStore>();

export function resetFixtureChatStore(): void {
  threadByVideo.clear();
}

export function fixtureGetOrCreateThread(videoId: string): ChatThread {
  const existing = threadByVideo.get(videoId);
  if (existing) return existing.thread;

  const thread: ChatThread = {
    id: crypto.randomUUID(),
    workspace_id: WS,
    scope_kind: "video",
    scope_id: videoId,
    title: "Fixture lesson chat",
    created_by: ACTOR,
    created_at: new Date().toISOString(),
  };
  threadByVideo.set(videoId, { thread, messages: [] });
  return thread;
}

export function fixtureThreadScope(threadId: string): string | null {
  for (const store of threadByVideo.values()) {
    if (store.thread.id === threadId) return store.thread.scope_id;
  }
  return null;
}

export function appendFixtureExchange(input: {
  threadId: string;
  question: string;
  answer: string;
  explanationMode: string;
}): PostChatResult {
  const store = [...threadByVideo.values()].find((s) => s.thread.id === input.threadId);
  if (!store) {
    throw Object.assign(new Error("Thread not found"), { code: "NOT_FOUND", status: 404 });
  }
  const now = new Date().toISOString();
  const user: ChatMessage = {
    id: crypto.randomUUID(),
    thread_id: store.thread.id,
    workspace_id: WS,
    role: "user",
    content: input.question.trim(),
    explanation_mode: input.explanationMode,
    unsupported: false,
    claims: [],
    analogies: [],
    citations: [],
    created_at: now,
    stream_state: "complete",
  };
  const assistant: ChatMessage = {
    id: crypto.randomUUID(),
    thread_id: store.thread.id,
    workspace_id: WS,
    role: "assistant",
    content: input.answer,
    explanation_mode: input.explanationMode,
    confidence_label: "model",
    unsupported: false,
    claims: [],
    analogies: [],
    citations: [],
    created_at: now,
    stream_state: "complete",
  };
  store.messages.push(user, assistant);
  return {
    user_message: user,
    assistant_message: assistant,
    unsupported: false,
    confidence_label: "model",
    explanation_mode: input.explanationMode,
  };
}

export function fixtureListMessages(threadId: string): ChatMessage[] {
  for (const store of threadByVideo.values()) {
    if (store.thread.id === threadId) return structuredClone(store.messages);
  }
  return [];
}

export function fixturePostMessage(input: {
  threadId: string;
  question: string;
  explanationMode: string;
  /** Force a recoverable failure for tests/UI. */
  forceError?: boolean;
}): PostChatResult {
  const store = [...threadByVideo.values()].find((s) => s.thread.id === input.threadId);
  if (!store) {
    throw Object.assign(new Error("Thread not found"), { code: "NOT_FOUND", status: 404 });
  }

  if (input.forceError || /FORCE_CHAT_ERROR/i.test(input.question)) {
    throw Object.assign(new Error("Fixture chat provider unavailable. Retry when ready."), {
      code: "PROVIDER_UNAVAILABLE",
      status: 503,
    });
  }

  const now = new Date().toISOString();
  const user: ChatMessage = {
    id: crypto.randomUUID(),
    thread_id: store.thread.id,
    workspace_id: WS,
    role: "user",
    content: input.question.trim(),
    explanation_mode: input.explanationMode,
    unsupported: false,
    claims: [],
    analogies: [],
    citations: [],
    created_at: now,
    stream_state: "complete",
  };

  const q = input.question.toLowerCase();
  let content =
    "Fixture answer: Active listening begins with attention, then clarifying questions, then a shared close. (synthetic)";
  let citations: Citation[] = [
    timedCitation(
      "c_01",
      SEG.s1,
      FIXTURE_SNIPPETS[0]!.text,
      FIXTURE_SNIPPETS[0]!.start_ms!,
      FIXTURE_SNIPPETS[0]!.end_ms!,
    ),
  ];
  let analogies: ChatMessage["analogies"] = [];
  let unsupported = false;
  let confidence = "supported";

  if (q.includes("restate") || q.includes("review")) {
    content =
      "Fixture answer: Restate requirements before feedback so both sides share the same problem statement. (synthetic)";
    citations = [
      timedCitation(
        "c_02",
        SEG.s2,
        FIXTURE_SNIPPETS[1]!.text,
        FIXTURE_SNIPPETS[1]!.start_ms!,
        FIXTURE_SNIPPETS[1]!.end_ms!,
      ),
    ];
  } else if (q.includes("without") || q.includes("exact time") || q.includes("untimed")) {
    content =
      "Fixture answer: Some uploaded TXT segments lack timecodes; the source is available without an exact jump. (synthetic)";
    citations = [untimedCitation("c_03", SEG.s5, FIXTURE_SNIPPETS[4]!.text)];
  } else if (q.includes("not covered") || q.includes("abstain")) {
    content =
      "Fixture abstention: That topic is not covered in the permitted transcript evidence. (synthetic)";
    citations = [];
    unsupported = true;
    confidence = "not_covered";
  }

  if (input.explanationMode === "simple") {
    analogies = [
      {
        text: "Like pausing a podcast to confirm you heard the same story. (AI illustration)",
        origin: "ai_generated_illustration",
      },
    ];
  } else if (input.explanationMode === "technical") {
    content += " Technical framing: treat restatement as an explicit handshake before mutation.";
  }

  const assistant: ChatMessage = {
    id: crypto.randomUUID(),
    thread_id: store.thread.id,
    workspace_id: WS,
    role: "assistant",
    content,
    explanation_mode: input.explanationMode,
    confidence_label: confidence,
    unsupported,
    claims: unsupported
      ? []
      : [
          {
            text: content.replace(/^Fixture (answer|abstention):\s*/i, "").slice(0, 120),
            citation_segment_ids: citations.map((c) => c.segment_id),
          },
        ],
    analogies,
    citations,
    provider_run_id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    stream_state: "complete",
  };

  store.messages.push(user, assistant);
  return {
    user_message: structuredClone(user),
    assistant_message: structuredClone(assistant),
    unsupported,
    confidence_label: confidence,
    explanation_mode: input.explanationMode,
  };
}
