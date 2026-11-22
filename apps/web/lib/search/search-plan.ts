export type SearchPlan = {
  queries: string[];
  keywords: string[];
  score: number;
  accepted: boolean;
  note: string;
};

const STOP = new Set([
  "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "from", "this", "that",
  "what", "how", "why", "is", "are", "was", "were", "be", "about", "into", "using", "use",
  "video", "lesson", "explain", "please", "does", "do", "can", "you", "it", "its", "their",
  "when", "where", "who", "which", "your", "our", "not", "but", "if", "as", "at", "by",
]);

const ACCEPTED_NOTE = "Searched academic papers and official documents.";
const REJECTED_NOTE = "Search words were not strong enough, so this answer stays with the lesson.";

function runtimeEnv(name: string): string {
  return (process.env[name] ?? "").trim();
}

export function contentTokens(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9][a-z0-9+-]{2,}/g) ?? []).filter(
    (token) => token.length >= 3 && !STOP.has(token),
  );
}

function unique(values: string[]): string[] {
  const seen = new Set<string>();
  const rows: string[] = [];
  for (const value of values) {
    const key = value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    rows.push(value);
  }
  return rows;
}

export function proposeSearchTerms(input: { title: string; summary: string; question: string }): {
  queries: string[];
  keywords: string[];
} {
  const lesson = contentTokens(`${input.title} ${input.summary}`);
  const asked = contentTokens(input.question);
  const counts = new Map<string, number>();
  for (const token of lesson) counts.set(token, (counts.get(token) ?? 0) + 1);
  const ranked = unique(lesson).sort((left, right) => {
    const shared = Number(asked.includes(right)) - Number(asked.includes(left));
    if (shared !== 0) return shared;
    return (counts.get(right) ?? 0) - (counts.get(left) ?? 0);
  });
  const keywords = ranked.slice(0, 5);
  const question = input.question.replace(/[?]+$/g, "").replace(/\s+/g, " ").trim();
  const extra = keywords.filter((token) => !asked.includes(token)).slice(0, 3);
  const query = [question, ...extra].filter(Boolean).join(" ").slice(0, 180);
  return {
    queries: query.length >= 8 ? [query] : [],
    keywords,
  };
}

export function validateSearchPlan(input: {
  title: string;
  summary: string;
  question: string;
  queries: string[];
  keywords: string[];
}): SearchPlan {
  const lesson = new Set(contentTokens(`${input.title} ${input.summary}`));
  const asked = new Set(contentTokens(input.question));
  const queries = unique(
    input.queries.map((query) => query.replace(/\s+/g, " ").trim()).filter((query) => query.length >= 8),
  ).slice(0, 2);
  const keywords = unique(
    input.keywords.map((keyword) => keyword.replace(/\s+/g, " ").trim()).filter((keyword) => contentTokens(keyword).length > 0),
  ).slice(0, 6);
  const used = new Set([...queries, ...keywords].flatMap(contentTokens));
  const lessonHits = [...used].filter((token) => lesson.has(token)).length;
  const questionHits = [...used].filter((token) => asked.has(token)).length;
  const lessonScore = lesson.size === 0 ? 0 : Math.min(1, lessonHits / Math.min(4, lesson.size));
  const questionScore = asked.size === 0 ? 0 : Math.min(1, questionHits / Math.min(3, asked.size));
  let score = Math.round(100 * (0.55 * lessonScore + 0.45 * questionScore));
  if (keywords.length < 2) score = Math.min(score, 40);
  if (queries.length === 0) score = 0;
  const accepted = score >= 60 && queries.length > 0 && keywords.length >= 2 && lessonHits >= 2;
  return {
    queries: accepted ? queries.map((query) => query.slice(0, 180)) : [],
    keywords: keywords.map((keyword) => keyword.slice(0, 80)),
    score,
    accepted,
    note: accepted ? ACCEPTED_NOTE : REJECTED_NOTE,
  };
}

async function draftWithGemini(input: {
  title: string;
  summary: string;
  question: string;
}): Promise<{ queries: string[]; keywords: string[] } | null> {
  const apiKey = runtimeEnv("GEMINI_API_KEY");
  if (!apiKey) return null;
  const configured = runtimeEnv("AI_CHAT_MODEL");
  const model = /gemini-2\.5|gemini-2\.0|gemini-1\./i.test(configured)
    ? "gemini-3.5-flash-lite"
    : configured || "gemini-3.5-flash-lite";
  const prompt = [
    "Write web search terms for academic papers and official documentation.",
    "Use words from the lesson and the question. Do not use generic words like video or explain.",
    "Return JSON with keys queries (1 or 2 strings) and keywords (3 to 6 short strings).",
    `Title: ${input.title.slice(0, 180)}`,
    `Lesson: ${input.summary.slice(0, 2_000)}`,
    `Question: ${input.question.slice(0, 500)}`,
  ].join("\n");
  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          contents: [{ role: "user", parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.1, responseMimeType: "application/json", maxOutputTokens: 400 },
        }),
        signal: AbortSignal.timeout(8_000),
      },
    );
    if (!res.ok) return null;
    const body = (await res.json().catch(() => null)) as {
      candidates?: { content?: { parts?: { text?: string }[] } }[];
    } | null;
    const text = body?.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join("") || "";
    const parsed = JSON.parse(text) as { queries?: unknown; keywords?: unknown };
    const queries = Array.isArray(parsed.queries) ? parsed.queries.map((item) => String(item)) : [];
    const keywords = Array.isArray(parsed.keywords) ? parsed.keywords.map((item) => String(item)) : [];
    if (queries.length === 0 && keywords.length === 0) return null;
    return { queries, keywords };
  } catch {
    return null;
  }
}

export async function buildSearchPlan(input: {
  title: string;
  summary: string;
  question: string;
}): Promise<SearchPlan> {
  const drafted = await draftWithGemini(input);
  const local = proposeSearchTerms(input);
  const scored = [drafted, local]
    .filter((candidate): candidate is { queries: string[]; keywords: string[] } => candidate !== null)
    .map((candidate) => validateSearchPlan({ ...input, ...candidate }));
  scored.sort((left, right) => Number(right.accepted) - Number(left.accepted) || right.score - left.score);
  return (
    scored[0] ?? {
      queries: [],
      keywords: [],
      score: 0,
      accepted: false,
      note: REJECTED_NOTE,
    }
  );
}
