/**
 * Which Gemini models build a lesson from a YouTube video, and in what order.
 *
 * Lessons stay on Gemini (it reads a public YouTube URL directly) and on the
 * low-cost Flash-Lite tier only. When one model is busy or returns nothing,
 * the route moves to the next: the configured model first when it is
 * Flash-Lite, then the newest stable Flash-Lite models the key can reach, then
 * Google's "gemini-flash-lite-latest" alias. The route makes a second pass
 * after a short wait, because "high demand" errors usually clear in seconds.
 * The list comes from the Gemini models endpoint, so a new Flash-Lite release
 * is picked up without a code change.
 */

const STABLE_FLASH_LITE = /^gemini-(\d+)(?:\.(\d+))?-flash-lite$/;
const RETIRED = /^gemini-(?:1\.|2\.0|2\.5)/i;
const MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200";
const CACHE_MS = 60 * 60 * 1000;

/** Used when the models endpoint cannot be read. Newest first. */
export const FALLBACK_LESSON_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"] as const;

/** Google's moving Flash-Lite alias. Last in the chain: it usually points at a model already tried. */
export const LITE_LATEST_ALIAS = "gemini-flash-lite-latest";

/** Models per pass. */
export const MAX_LESSON_MODELS = 4;

type Stable = { name: string; major: number; minor: number };

function parseStableLite(name: string): Stable | null {
  const match = STABLE_FLASH_LITE.exec(name);
  if (!match || RETIRED.test(name)) return null;
  return { name, major: Number(match[1]), minor: Number(match[2] ?? 0) };
}

export function isLessonModel(name: string): boolean {
  return name === LITE_LATEST_ALIAS || parseStableLite(name) !== null;
}

/** Stable Flash-Lite models, newest first. Flash, Pro, previews, TTS, and image models are left out. */
export function newestFlashLiteFirst(names: readonly string[]): string[] {
  const stable = names.map(parseStableLite).filter((item): item is Stable => item !== null);
  stable.sort((a, b) => (a.major !== b.major ? b.major - a.major : b.minor - a.minor));
  return stable.map((item) => item.name);
}

/**
 * Model order for one pass of a lesson build. `available` is the key's model
 * list, or null when it could not be read. A configured model that is not
 * Flash-Lite (a pricier Gemini tier, or another provider's id when the API
 * runs elsewhere) or that the key cannot reach is skipped.
 */
export function lessonModelChain(configured: string, available: readonly string[] | null): string[] {
  const reachable = (name: string) => available === null || available.includes(name);
  const first = isLessonModel(configured) && reachable(configured) ? [configured] : [];
  const newest = available === null ? [...FALLBACK_LESSON_MODELS] : newestFlashLiteFirst(available);
  const alias = reachable(LITE_LATEST_ALIAS) ? [LITE_LATEST_ALIAS] : [];
  const chain: string[] = [];
  for (const name of [...first, ...newest, ...alias]) {
    if (!chain.includes(name)) chain.push(name);
  }
  return chain.slice(0, MAX_LESSON_MODELS);
}

/** Busy, timed out, missing, or unable to take this input: another try may work. Key or permission errors stop. */
export function shouldTryNextModel(status: number, message: string): boolean {
  if (status === 401 || status === 403) return false;
  if ([404, 408, 429, 500, 502, 503, 504].includes(status)) return true;
  return /high demand|try again|no longer available|not found|unavailable|overloaded|not supported|does not support|deadline/i.test(
    message,
  );
}

let cached: { at: number; names: string[] } | null = null;

/** Gemini model ids that support generateContent for this key, cached for an hour. Null when the list cannot be read. */
export async function listGeminiModels(apiKey: string, now: number = Date.now()): Promise<string[] | null> {
  if (cached && now - cached.at < CACHE_MS) return cached.names;
  try {
    const res = await fetch(MODELS_URL, {
      headers: { "x-goog-api-key": apiKey },
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return null;
    const body = (await res.json().catch(() => null)) as {
      models?: { name?: string; supportedGenerationMethods?: string[] }[];
    } | null;
    const names = (body?.models ?? [])
      .filter((model) => model.supportedGenerationMethods?.includes("generateContent"))
      .map((model) => (model.name ?? "").replace(/^models\//, ""))
      .filter(Boolean);
    if (names.length === 0) return null;
    cached = { at: now, names };
    return names;
  } catch {
    return null;
  }
}

/** Tests only. */
export function resetGeminiModelCache(): void {
  cached = null;
}
