import { NextResponse } from "next/server";

import { askGeminiLesson } from "@/lib/lesson/gemini-ask";

export const maxDuration = 90;

export async function POST(request: Request) {
  const payload = (await request.json().catch(() => null)) as {
    question?: string;
    transcript?: string;
    title?: string;
    explanationMode?: string;
    externalSearch?: boolean;
    packedHistory?: string;
  } | null;
  const result = await askGeminiLesson({
    question: payload?.question || "",
    transcript: payload?.transcript || "",
    title: payload?.title,
    explanationMode: payload?.explanationMode,
    externalSearch: Boolean(payload?.externalSearch),
    packedHistory: payload?.packedHistory,
  });
  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }
  return NextResponse.json({ answer: JSON.stringify(result.answer) });
}
