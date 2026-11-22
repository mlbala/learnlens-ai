import { NextResponse } from "next/server";

export const maxDuration = 120;

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

type LessonPayload = {
  title?: string;
  summary?: string;
  key_points?: string[];
  transcript?: string;
};

function runtimeEnv(name: string): string {
  return (process.env[name] ?? "").trim();
}

function youtubeUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

async function gemini(parts: unknown[], model: string, apiKey: string) {
  const endpoint =
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=` +
    encodeURIComponent(apiKey);
  let res: Response;
  try {
    res = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts }],
        generationConfig: { temperature: 0.2, responseMimeType: "application/json" },
      }),
      signal: AbortSignal.timeout(25_000),
    });
  } catch {
    return { ok: false as const, status: 503, message: "Gemini timed out while reading the video." };
  }
  const body = (await res.json().catch(() => null)) as {
    error?: { message?: string };
    candidates?: { content?: { parts?: { text?: string }[] } }[];
  } | null;
  if (!res.ok) {
    const message = body?.error?.message || `Gemini request failed (${res.status})`;
    return { ok: false as const, status: res.status, message };
  }
  const text = body?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("") || "";
  return { ok: true as const, text };
}

export async function POST(request: Request) {
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
    "Watch this public YouTube video. Return compact JSON with keys title, summary (one paragraph), key_points (up to 6 short strings), and transcript (the main spoken points in a few paragraphs). Do not invent timestamps. If you cannot access the video, set summary and transcript to empty strings.";

  const parts = [
    {
      fileData: {
        mimeType: "video/mp4",
        fileUri: youtubeUrl(videoId),
      },
    },
    { text: prompt },
  ];
  const retired = /gemini-2\.5|gemini-2\.0|gemini-1\./i;
  const models = [configured, "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"].filter(
    (name, index, all): name is string => Boolean(name) && !retired.test(name) && all.indexOf(name) === index,
  );
  let result: Awaited<ReturnType<typeof gemini>> | null = null;
  for (const candidate of models) {
    result = await gemini(parts, candidate, apiKey);
    if (result.ok) break;
    const retryable =
      result.status === 404 ||
      result.status === 429 ||
      result.status === 503 ||
      /high demand|try again|no longer available|not found|unavailable|overloaded/i.test(result.message);
    if (!retryable) break;
  }
  if (!result?.ok) {
    return NextResponse.json(
      { error: result?.message || "Gemini could not read this video." },
      { status: 502 },
    );
  }

  let lesson: LessonPayload = {};
  try {
    lesson = JSON.parse(result.text) as LessonPayload;
  } catch {
    lesson = { summary: result.text, transcript: result.text, key_points: [] };
  }
  if (!lesson.summary && !lesson.transcript) {
    return NextResponse.json(
      { error: "Gemini could not read this video. It may be private, age-gated, or too long." },
      { status: 422 },
    );
  }

  return NextResponse.json({
    videoId,
    title: lesson.title || "",
    summary: lesson.summary || "",
    key_points: Array.isArray(lesson.key_points) ? lesson.key_points.map(String).slice(0, 8) : [],
    transcript: lesson.transcript || lesson.summary || "",
  });
}
