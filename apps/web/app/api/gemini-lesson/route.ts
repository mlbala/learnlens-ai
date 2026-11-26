import { NextResponse } from "next/server";

import { lessonModelChain, listGeminiModels, shouldTryNextModel } from "@/lib/lesson/gemini-models";
import { recoverLessonFields } from "@/lib/lesson/notes";
import { toLessonTitle } from "@/lib/lesson/title";

export const maxDuration = 180;

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
/** All model attempts for one lesson finish inside this, under maxDuration. */
const BUILD_BUDGET_MS = 170_000;
/** One model reading one video. Longer videos need more than a short chat call. */
const ATTEMPT_TIMEOUT_MS = 60_000;
/** Not worth starting another video read with less time than this left. */
const MIN_ATTEMPT_MS = 8_000;
/** Passes over the Flash-Lite chain. "High demand" errors usually clear within seconds. */
const LESSON_PASSES = 2;
const PASS_BACKOFF_MS = 3_000;

const UNREADABLE = "Gemini could not read this video. It may be private, age-gated, or too long.";

type LessonPayload = {
  title?: string;
  summary?: string;
  key_points?: string[];
  transcript?: string;
};

type BuiltLesson = {
  title: string;
  summary: string;
  key_points: string[];
  transcript: string;
};

/** Model id and what happened: ok, timeout, an HTTP status, or empty:<finish reason>. No lesson text. */
type Attempt = { model: string; outcome: string };

function runtimeEnv(name: string): string {
  return (process.env[name] ?? "").trim();
}

function youtubeUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

async function gemini(parts: unknown[], model: string, apiKey: string, timeoutMs: number) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
  let res: Response;
  try {
    res = await fetch(endpoint, {
      method: "POST",
      // Key in a header, not the URL, so it stays out of request logs.
      headers: { "content-type": "application/json", "x-goog-api-key": apiKey },
      body: JSON.stringify({
        contents: [{ role: "user", parts }],
        generationConfig: {
          temperature: 0.2,
          responseMimeType: "application/json",
          maxOutputTokens: 4096,
        },
      }),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    return {
      ok: false as const,
      status: 503,
      timedOut: true,
      message: "Gemini timed out while reading the video.",
    };
  }
  const body = (await res.json().catch(() => null)) as {
    error?: { message?: string };
    candidates?: { finishReason?: string; content?: { parts?: { text?: string }[] } }[];
    promptFeedback?: { blockReason?: string };
  } | null;
  if (!res.ok) {
    const message = body?.error?.message || `Gemini request failed (${res.status})`;
    return { ok: false as const, status: res.status, timedOut: false, message };
  }
  const candidate = body?.candidates?.[0];
  const text = candidate?.content?.parts?.map((p) => p.text || "").join("") || "";
  const finish = candidate?.finishReason || body?.promptFeedback?.blockReason || "NO_CANDIDATE";
  return { ok: true as const, text, finish };
}

/** The lesson fields from one model reply, or null when the model could not read the video. */
function readLesson(text: string): BuiltLesson | null {
  let parsed: LessonPayload = {};
  try {
    const value: unknown = JSON.parse(text);
    // Some Flash-Lite models wrap the object in an array: [{ "title": ... }].
    const object = Array.isArray(value) ? value.find((item) => item && typeof item === "object") : value;
    parsed = (object && typeof object === "object" ? object : {}) as LessonPayload;
  } catch {
    parsed = { summary: text, transcript: text, key_points: [] };
  }
  const lesson = recoverLessonFields({
    summary: parsed.summary || "",
    key_points: parsed.key_points,
    transcript: parsed.transcript,
  });
  if (!lesson.summary && !lesson.transcript) return null;
  return {
    title: toLessonTitle(parsed.title || ""),
    summary: lesson.summary || "",
    key_points: lesson.keyPoints,
    transcript: lesson.transcript || lesson.summary || "",
  };
}

function logBuild(videoId: string, attempts: Attempt[], model: string | null): void {
  // Model ids and status codes only. No lesson text.
  console.info(
    JSON.stringify({
      event: "gemini_lesson_build",
      youtube_video_id: videoId,
      model,
      attempts: attempts.map((item) => `${item.model}:${item.outcome}`),
    }),
  );
}

export async function POST(request: Request) {
  const started = Date.now();
  const apiKey = runtimeEnv("GEMINI_API_KEY");
  const configured = runtimeEnv("AI_CHAT_MODEL");
  if (!apiKey) {
    return NextResponse.json(
      { error: "GEMINI_API_KEY is not set on the web server." },
      { status: 503 },
    );
  }

  const payload = (await request.json().catch(() => null)) as { videoId?: string } | null;
  const videoId = payload?.videoId ?? "";
  if (!VIDEO_ID_RE.test(videoId) || videoId.startsWith("vid")) {
    return NextResponse.json({ error: "A public 11-character YouTube video id is required." }, { status: 400 });
  }

  const prompt =
    "Watch this public YouTube video. Return compact JSON with keys title, summary, key_points, and transcript. Summary is two or three short paragraphs of plain sentences. key_points is up to 6 complete sentences. Transcript is the main spoken points in a few paragraphs. Title is a short plain name with no emoji, hashtags, or decoration. Do not invent timestamps. If you cannot access the video, set summary and transcript to empty strings.";

  const parts = [
    {
      fileData: {
        mimeType: "video/mp4",
        fileUri: youtubeUrl(videoId),
      },
    },
    { text: prompt },
  ];

  const models = lessonModelChain(configured, await listGeminiModels(apiKey));
  const attempts: Attempt[] = [];
  let lastError = "";
  let stopped = false;
  passes: for (let pass = 0; pass < LESSON_PASSES && !stopped; pass += 1) {
    if (pass > 0) {
      if (BUILD_BUDGET_MS - (Date.now() - started) < PASS_BACKOFF_MS + MIN_ATTEMPT_MS) break;
      await new Promise((resolve) => setTimeout(resolve, PASS_BACKOFF_MS));
    }
    for (const model of models) {
      const left = BUILD_BUDGET_MS - (Date.now() - started);
      if (left < MIN_ATTEMPT_MS) break passes;
      const result = await gemini(parts, model, apiKey, Math.min(ATTEMPT_TIMEOUT_MS, left));
      if (!result.ok) {
        attempts.push({ model, outcome: result.timedOut ? "timeout" : String(result.status) });
        lastError = result.message;
        if (!shouldTryNextModel(result.status, result.message)) {
          stopped = true;
          break;
        }
        continue;
      }
      const lesson = readLesson(result.text);
      if (!lesson) {
        // Nothing usable from this model this time; the next model or the next pass may still read the video.
        attempts.push({ model, outcome: `empty:${result.finish}` });
        continue;
      }
      attempts.push({ model, outcome: "ok" });
      logBuild(videoId, attempts, model);
      return NextResponse.json({ videoId, ...lesson, model });
    }
  }

  logBuild(videoId, attempts, null);
  if (attempts.some((item) => item.outcome.startsWith("empty"))) {
    return NextResponse.json({ error: UNREADABLE }, { status: 422 });
  }
  return NextResponse.json(
    { error: lastError || "Gemini could not read this video." },
    { status: 502 },
  );
}
