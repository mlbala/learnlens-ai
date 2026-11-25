// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as buildLesson } from "@/app/api/gemini-lesson/route";
import {
  FALLBACK_LESSON_MODELS,
  lessonModelChain,
  listGeminiModels,
  newestFlashLiteFirst,
  resetGeminiModelCache,
  shouldTryNextModel,
} from "@/lib/lesson/gemini-models";

const LISTED = [
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "gemini-3-flash-preview",
  "gemini-3.1-flash-lite",
  "gemini-3.1-flash-lite-preview",
  "gemini-3.1-pro-preview",
  "gemini-3.5-flash",
  "gemini-3.5-flash-lite",
  "gemini-3.6-flash",
  "gemini-3.8-flash",
  "gemini-3.8-flash-lite-tts",
  "gemini-4-argon",
  "gemini-flash-latest",
  "gemini-flash-lite-latest",
];

describe("Gemini lesson model order (Flash-Lite only)", () => {
  it("keeps stable Flash-Lite newest first and leaves out Flash, Pro, previews, TTS, and retired ids", () => {
    expect(newestFlashLiteFirst(LISTED)).toEqual(["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]);
  });

  it("compares minor versions as numbers", () => {
    expect(
      newestFlashLiteFirst(["gemini-3.9-flash-lite", "gemini-3.10-flash-lite", "gemini-4-flash-lite"]),
    ).toEqual(["gemini-4-flash-lite", "gemini-3.10-flash-lite", "gemini-3.9-flash-lite"]);
  });

  it("tries the configured Flash-Lite model first, then the newest, then the lite alias, without repeats", () => {
    expect(lessonModelChain("gemini-3.5-flash-lite", LISTED)).toEqual([
      "gemini-3.5-flash-lite",
      "gemini-3.1-flash-lite",
      "gemini-flash-lite-latest",
    ]);
    expect(lessonModelChain("gemini-3.1-flash-lite", LISTED)[0]).toBe("gemini-3.1-flash-lite");
  });

  it("never adds a pricier tier, another provider's id, a retired id, or a model the key cannot reach", () => {
    for (const configured of ["gemini-3.8-flash", "gemini-3.1-pro-preview", "gpt-5.4-mini", "gemini-2.5-flash-lite", "gemini-9.9-flash-lite"]) {
      const chain = lessonModelChain(configured, LISTED);
      expect(chain).not.toContain(configured);
      expect(chain.every((name) => name.includes("flash-lite"))).toBe(true);
    }
  });

  it("uses the built-in Flash-Lite list when the model list cannot be read", () => {
    expect(lessonModelChain("", null)).toEqual([...FALLBACK_LESSON_MODELS, "gemini-flash-lite-latest"]);
  });

  it("moves on for busy, timed out, or missing models and stops on key errors", () => {
    expect(shouldTryNextModel(503, "This model is currently experiencing high demand.")).toBe(true);
    expect(shouldTryNextModel(429, "Resource exhausted")).toBe(true);
    expect(shouldTryNextModel(404, "models/x is not found")).toBe(true);
    expect(shouldTryNextModel(504, "Deadline exceeded")).toBe(true);
    expect(shouldTryNextModel(400, "Video input is not supported for this model")).toBe(true);
    expect(shouldTryNextModel(400, "API key not valid. Please pass a valid API key.")).toBe(false);
    expect(shouldTryNextModel(403, "Permission denied")).toBe(false);
  });
});

function modelsResponse(names: string[]): Response {
  return Response.json({
    models: names.map((name) => ({
      name: `models/${name}`,
      supportedGenerationMethods: ["generateContent"],
    })),
  });
}

function lessonReply(lesson: Record<string, unknown>): Response {
  return Response.json({
    candidates: [{ content: { parts: [{ text: JSON.stringify(lesson) }] } }],
  });
}

function busy(): Response {
  return Response.json(
    { error: { code: 503, message: "This model is currently experiencing high demand." } },
    { status: 503 },
  );
}

const EMPTY = { summary: "", transcript: "" };
const GOOD_LESSON = {
  title: "How Transformers Work",
  summary: "A transformer moves energy between two coils through a shared magnetic field.",
  key_points: ["Turns ratio sets the voltage change."],
  transcript: "The primary coil makes a changing magnetic field that induces a voltage in the secondary coil.",
};

function lessonRequest(videoId = "UchitHGF4n8"): Request {
  return new Request("http://localhost/api/gemini-lesson", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ videoId }),
  });
}

/** Runs the route while stepping the fake clock, so the pass backoff takes no real time. */
async function build(request: Request = lessonRequest()): Promise<Response> {
  let done = false;
  const pending = buildLesson(request).finally(() => {
    done = true;
  });
  while (!done) await vi.advanceTimersByTimeAsync(500);
  return pending;
}

function calledModels(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes(":generateContent"))
    .map((url) => decodeURIComponent(url.split("/models/")[1]!.split(":")[0]!));
}

describe("POST /api/gemini-lesson Flash-Lite fallback with retry", () => {
  beforeEach(() => {
    resetGeminiModelCache();
    // Only setTimeout (the pass backoff) is faked; Date.now, the time budget, stays real.
    vi.useFakeTimers({ toFake: ["setTimeout"] });
    vi.stubEnv("GEMINI_API_KEY", "test-key");
    vi.stubEnv("AI_CHAT_MODEL", "gemini-3.5-flash-lite");
    vi.spyOn(console, "info").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("moves past empty and busy replies to the next Flash-Lite model and keeps the key out of URLs", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (!url.includes(":generateContent")) return modelsResponse(LISTED);
      if (url.includes("gemini-3.5-flash-lite:")) return lessonReply(EMPTY);
      if (url.includes("gemini-3.1-flash-lite:")) return busy();
      return lessonReply(GOOD_LESSON);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(200);
    const body = (await response.json()) as { model?: string; summary?: string };
    expect(body.model).toBe("gemini-flash-lite-latest");
    expect(body.summary).toContain("magnetic field");
    expect(calledModels(fetchMock)).toEqual([
      "gemini-3.5-flash-lite",
      "gemini-3.1-flash-lite",
      "gemini-flash-lite-latest",
    ]);
    for (const [url, init] of fetchMock.mock.calls as unknown as [string, RequestInit][]) {
      expect(url).not.toContain("test-key");
      expect(new Headers(init?.headers).get("x-goog-api-key")).toBe("test-key");
    }
  });

  it("retries the chain once more when every model was busy on the first pass", async () => {
    let calls = 0;
    const fetchMock = vi.fn(async (url: string) => {
      if (!url.includes(":generateContent")) return modelsResponse(LISTED);
      calls += 1;
      return calls <= 3 ? busy() : lessonReply(GOOD_LESSON);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(200);
    expect(((await response.json()) as { model?: string }).model).toBe("gemini-3.5-flash-lite");
    expect(calledModels(fetchMock)).toEqual([
      "gemini-3.5-flash-lite",
      "gemini-3.1-flash-lite",
      "gemini-flash-lite-latest",
      "gemini-3.5-flash-lite",
    ]);
  });

  it("only ever calls Flash-Lite models, even when a pricier model is configured", async () => {
    vi.stubEnv("AI_CHAT_MODEL", "gemini-3.8-flash");
    const fetchMock = vi.fn(async (url: string) =>
      url.includes(":generateContent") ? busy() : modelsResponse(LISTED),
    );
    vi.stubGlobal("fetch", fetchMock);

    await build();
    expect(calledModels(fetchMock).every((name) => name.includes("flash-lite"))).toBe(true);
  });

  it("stops at once on a key error, with no second pass", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (!url.includes(":generateContent")) return modelsResponse(LISTED);
      return Response.json({ error: { message: "Permission denied" } }, { status: 403 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(502);
    expect(calledModels(fetchMock)).toEqual(["gemini-3.5-flash-lite"]);
  });

  it("returns 502 with the last error after two busy passes", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes(":generateContent") ? busy() : modelsResponse(LISTED),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(502);
    expect(((await response.json()) as { error: string }).error).toMatch(/high demand/);
    expect(calledModels(fetchMock)).toHaveLength(6);
  });

  it("returns 422 when the models that answered could not read the video", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (!url.includes(":generateContent")) return modelsResponse(LISTED);
      return url.includes("gemini-3.1-flash-lite:") ? busy() : lessonReply(EMPTY);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(422);
    expect(((await response.json()) as { error: string }).error).toMatch(/could not read this video/);
  });

  it("reads a lesson that the model wrapped in a JSON array", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (!url.includes(":generateContent")) return modelsResponse(LISTED);
      return Response.json({
        candidates: [{ finishReason: "STOP", content: { parts: [{ text: JSON.stringify([GOOD_LESSON]) }] } }],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(200);
    const body = (await response.json()) as { title?: string; summary?: string };
    expect(body.title).toBe("How Transformers Work");
    expect(body.summary).toContain("magnetic field");
    expect(calledModels(fetchMock)).toHaveLength(1);
  });

  it("falls back to the built-in Flash-Lite list when the models endpoint fails", async () => {
    vi.stubEnv("AI_CHAT_MODEL", "");
    const fetchMock = vi.fn(async (url: string) => {
      if (!url.includes(":generateContent")) return new Response("down", { status: 500 });
      return lessonReply(GOOD_LESSON);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await build();
    expect(response.status).toBe(200);
    expect(calledModels(fetchMock)).toEqual([FALLBACK_LESSON_MODELS[0]]);
  });

  it("reads the model list once per hour", async () => {
    const fetchMock = vi.fn(async () => modelsResponse(LISTED));
    vi.stubGlobal("fetch", fetchMock);
    await listGeminiModels("test-key", 1_000);
    await listGeminiModels("test-key", 1_000 + 30 * 60 * 1000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await listGeminiModels("test-key", 1_000 + 61 * 60 * 1000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
