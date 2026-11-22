import { NextResponse } from "next/server";

import { askGeminiLesson } from "@/lib/lesson/gemini-ask";
import { proxyLearningApi } from "@/lib/server/learning-api";

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
  const asked = await askGeminiLesson({
    question,
    transcript,
    title: payload?.title,
    explanationMode: payload?.explanationMode,
    externalSearch,
    packedHistory: prepared?.packed_history || "",
  });
  if (!asked.ok) {
    return NextResponse.json(
      { error: { code: "GEMINI_ASK_FAILED", message: asked.error } },
      { status: asked.status },
    );
  }
  return proxyLearningApi(request, `/api/v1/lesson-chat/videos/${videoId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      question,
      explanation_mode: payload?.explanationMode || "standard",
      external_search: externalSearch,
      answer: {
        lesson: asked.answer.lesson.map((section) => ({
          heading: section.heading.slice(0, 200),
          body: section.body.slice(0, 8_000),
        })),
        external: externalSearch
          ? asked.answer.external.map((section) => ({
              heading: section.heading.slice(0, 200),
              body: section.body.slice(0, 8_000),
            }))
          : [],
        sources: externalSearch
          ? asked.answer.sources.flatMap((source) =>
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
}
