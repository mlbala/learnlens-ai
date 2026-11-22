import { asTutorAnswer, type TutorAnswer } from "@/lib/lesson/answer";
import { buildLessonModelPrompt, type PromptEvidence } from "@/lib/lesson/model-prompt";
import type { ExplanationMode } from "@/lib/lesson/types";
import { searchTopicSources, type TopicSource } from "@/lib/search/topic-sources";

export type GeminiAskResult =
  | { ok: true; answer: TutorAnswer }
  | { ok: false; status: number; error: string };

function runtimeEnv(name: string): string {
  return (process.env[name] ?? "").trim();
}

function storedSources(sources: TopicSource[], externalSearch: boolean) {
  if (!externalSearch) return [];
  return sources
    .filter((source) => source.provider && source.url.startsWith("http"))
    .map((source) => ({
      title: source.title,
      url: source.url,
      kind: source.kind,
      provider: source.provider,
    }));
}

export async function askGeminiLesson(input: {
  question: string;
  transcript: string;
  title?: string;
  explanationMode?: ExplanationMode | string;
  externalSearch: boolean;
  packedHistory?: string;
  evidence?: PromptEvidence[];
  knownSources?: TopicSource[];
}): Promise<GeminiAskResult> {
  const apiKey = runtimeEnv("GEMINI_API_KEY");
  const configured = runtimeEnv("AI_CHAT_MODEL");
  const model = /gemini-2\.5|gemini-2\.0|gemini-1\./i.test(configured)
    ? "gemini-3.5-flash-lite"
    : configured || "gemini-3.5-flash-lite";
  if (!apiKey) {
    return { ok: false, status: 503, error: "GEMINI_API_KEY is not set on the web server." };
  }
  const question = input.question.trim();
  const transcript = input.transcript.slice(0, 80_000);
  if (!question || !transcript) {
    return { ok: false, status: 400, error: "Question and lesson text are required." };
  }

  const found = input.evidence
    ? (input.knownSources ?? [])
    : input.externalSearch
      ? await searchTopicSources(question)
      : [];
  const prompt = buildLessonModelPrompt({
    title: input.title,
    transcript,
    question,
    explanationMode: input.explanationMode,
    externalSearch: input.externalSearch,
    packedHistory: input.packedHistory,
    sources: storedSources(found, input.externalSearch),
    evidence: input.evidence,
  });
  const endpoint =
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=` +
    encodeURIComponent(apiKey);
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.2,
        maxOutputTokens: input.explanationMode === "simple" ? 700 : 2048,
        responseMimeType: "application/json",
      },
    }),
  });
  const body = (await res.json().catch(() => null)) as {
    error?: { message?: string };
    candidates?: { content?: { parts?: { text?: string }[] } }[];
  } | null;
  if (!res.ok) {
    return { ok: false, status: 502, error: body?.error?.message || "Gemini could not answer." };
  }
  const raw = body?.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join("") || "";
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = { v: 1, lesson: [{ heading: "Answer", body: raw }], external: [], sources: [] };
  }
  const draft = parsed as { lesson?: unknown; external?: unknown };
  const answer = asTutorAnswer({
    v: 1,
    lesson: draft.lesson,
    external: input.externalSearch ? draft.external : [],
    sources: storedSources(found, input.externalSearch),
  });
  if (!answer) {
    return { ok: false, status: 502, error: "Gemini did not return a lesson panel." };
  }
  return { ok: true, answer };
}
