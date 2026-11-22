import { NextResponse } from "next/server";

import { askGeminiLesson } from "@/lib/lesson/gemini-ask";
import { VIDEO_DOES_NOT_COVER, type PromptEvidence } from "@/lib/lesson/model-prompt";
import { proxyLearningApi } from "@/lib/server/learning-api";
import { searchTopicSources, type TopicSource } from "@/lib/search/topic-sources";
import type { TutorAnswer } from "@/lib/lesson/answer";

export const dynamic = "force-dynamic";
export const maxDuration = 90;

const VIDEO_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type LessonChatBody = {
  videoId?: string;
  question?: string;
  transcript?: string;
  title?: string;
  explanationMode?: string;
  externalSearch?: boolean;
};

export async function POST(request: Request) {
  const payload = (await request.json().catch(() => null)) as LessonChatBody | null;
  const videoId = payload?.videoId ?? "";
  const question = payload?.question?.trim() || "";
  const transcript = payload?.transcript || "";
  if (!VIDEO_ID_RE.test(videoId) || !question || !transcript.trim()) {
    return NextResponse.json(
      { error: { code: "INVALID_QUESTION", message: "A saved lesson and a question are required." } },
      { status: 400 },
    );
  }
  const externalSearch = Boolean(payload?.externalSearch);
  const prepare = await proxyLearningApi(
    request,
    `/api/v1/lesson-chat/videos/${videoId}/prepare`,
    {
      method: "POST",
      body: JSON.stringify({ external_search: externalSearch }),
    },
  );
  if (!prepare.ok) return prepare;
  const prepared = (await prepare.json().catch(() => null)) as { packed_history?: string } | null;
  const found = externalSearch ? await searchTopicSources(question) : [];
  const retrieved = await proxyLearningApi(
    request,
    `/api/v1/lesson-chat/videos/${videoId}/retrieve`,
    {
      method: "POST",
      body: JSON.stringify({
        question,
        external_search: externalSearch,
        sources: externalSearch ? searchHits(found) : [],
      }),
    },
  );
  const packet = (await retrieved.clone().json().catch(() => null)) as RetrievePacket | null;
  if (!retrieved.ok || !packet) return retrieved;
  const evidence = (packet.passages ?? []).map(toEvidence);
  const answer = await lessonAnswer({
    question,
    transcript,
    title: payload?.title,
    explanationMode: payload?.explanationMode,
    externalSearch,
    packedHistory: prepared?.packed_history || "",
    packet,
    evidence,
    found,
  });
  if (!answer.ok) {
    const busy = answer.error === "Gemini is busy.";
    return NextResponse.json(
      {
        error: {
          code: busy ? "GEMINI_BUSY" : "GEMINI_ASK_FAILED",
          message: busy ? "Gemini is busy." : "Gemini could not answer.",
        },
      },
      { status: answer.status },
    );
  }
  const saved = await proxyLearningApi(request, `/api/v1/lesson-chat/videos/${videoId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      question,
      explanation_mode: payload?.explanationMode || "standard",
      external_search: externalSearch,
      answer: {
        lesson: answer.answer.lesson.map((section) => ({
          heading: section.heading.slice(0, 200),
          body: section.body.slice(0, 8_000),
        })),
        external: externalSearch
          ? answer.answer.external.map((section) => ({
              heading: section.heading.slice(0, 200),
              body: section.body.slice(0, 8_000),
            }))
          : [],
        sources: externalSearch
          ? answer.answer.sources.flatMap((source) =>
              source.provider
                ? [
                    {
                      title: source.title,
                      url: source.url,
                      kind: source.kind,
                      provider: source.provider,
                    },
                  ]
                : [],
            )
          : [],
      },
    }),
  });
  copyCookies(retrieved, saved);
  return saved;
}

type RetrievePacket = {
  decision?: string;
  video_covered?: boolean;
  passages?: {
    id?: string;
    evidence_origin?: string;
    evidence_provider?: string;
    text?: string;
    title?: string;
    source_url?: string;
  }[];
};

function searchHits(sources: TopicSource[]) {
  return sources.flatMap((source) =>
    source.provider && source.url.startsWith("http")
      ? [
          {
            title: source.title,
            url: source.url,
            snippet: source.snippet,
            kind: source.kind,
            provider: source.provider,
          },
        ]
      : [],
  );
}

function toEvidence(row: NonNullable<RetrievePacket["passages"]>[number]): PromptEvidence {
  return {
    id: String(row.id || ""),
    evidence_origin: row.evidence_origin === "external_search" ? "external_search" : "video_transcript",
    text: String(row.text || ""),
  };
}

async function lessonAnswer(input: {
  question: string;
  transcript: string;
  title?: string;
  explanationMode?: string;
  externalSearch: boolean;
  packedHistory: string;
  packet: RetrievePacket;
  evidence: PromptEvidence[];
  found: TopicSource[];
}): Promise<{ ok: true; answer: TutorAnswer } | { ok: false; status: number; error: string }> {
  const blend = input.packet.decision === "blend";
  if (input.packet.decision === "abstain") {
    return {
      ok: true,
      answer: {
        v: 1,
        lesson: [{ heading: "Coverage", body: VIDEO_DOES_NOT_COVER }],
        external: [],
        sources: [],
      },
    };
  }
  const byUrl = new Map(input.found.map((source) => [source.url, source]));
  const knownSources = input.evidence
    .filter((block) => block.evidence_origin === "external_search")
    .map((block) => {
      const row = input.packet.passages?.find((passage) => passage.id === block.id);
      const url = row?.source_url || "";
      const known = byUrl.get(url);
      return (
        known ?? {
          title: row?.title || url,
          url,
          snippet: block.text,
          kind: "other" as const,
          provider: row?.evidence_provider as TopicSource["provider"],
        }
      );
    })
    .filter((source) => source.provider && source.url.startsWith("http"));
  const asked = await askGeminiLesson({
    question: input.question,
    transcript: input.transcript,
    title: input.title,
    explanationMode: input.explanationMode,
    externalSearch: blend,
    packedHistory: input.packedHistory,
    evidence: input.evidence,
    knownSources,
  });
  if (!asked.ok) return asked;
  const lesson = input.packet.video_covered
    ? asked.answer.lesson
    : [{ heading: "Coverage", body: VIDEO_DOES_NOT_COVER }];
  return {
    ok: true,
    answer: {
      v: 1,
      lesson,
      external: blend ? asked.answer.external : [],
      sources: blend ? asked.answer.sources : [],
    },
  };
}

function copyCookies(from: NextResponse, to: NextResponse) {
  const cookies = typeof from.headers.getSetCookie === "function" ? from.headers.getSetCookie() : [];
  for (const cookie of cookies) to.headers.append("set-cookie", cookie);
}
