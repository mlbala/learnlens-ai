export type AnswerSection = {
  heading: string;
  body: string;
};

export type SourceProvider = "tavily" | "semantic_scholar" | "openalex";

export type AnswerSource = {
  title: string;
  url: string;
  kind: "paper" | "official" | "other";
  provider?: SourceProvider;
};

export type ReviewStatus = "accepted" | "regenerated" | "withheld";

export type WebSearchPlan = {
  queries: string[];
  keywords: string[];
  score: number;
  accepted: boolean;
  note: string;
};

export type TutorAnswer = {
  v: 1;
  lesson: AnswerSection[];
  external: AnswerSection[];
  sources: AnswerSource[];
  review_status?: ReviewStatus;
  decision?: "lesson_only" | "blend" | "abstain";
  outside_lane_empty?: boolean;
  web_search?: WebSearchPlan;
};

function asSections(value: unknown): AnswerSection[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      const row = item as { heading?: unknown; body?: unknown };
      const heading = String(row?.heading || "").trim();
      const body = String(row?.body || "").replace(/\s+\n/g, "\n").trim();
      return { heading, body };
    })
    .filter((section) => section.heading && section.body);
}

function asProvider(value: unknown): SourceProvider | undefined {
  if (value === "tavily" || value === "semantic_scholar" || value === "openalex") return value;
  return undefined;
}

export function asTutorAnswer(value: unknown): TutorAnswer | null {
  if (!value || typeof value !== "object") return null;
  const data = value as Partial<TutorAnswer>;
  if (data.v !== 1) return null;
  const lesson = asSections(data.lesson);
  const external = asSections(data.external);
  if (lesson.length === 0 && external.length === 0) return null;
  const sources = Array.isArray(data.sources)
    ? data.sources
        .map((source) => {
          const row = source as Partial<AnswerSource>;
          const kind: AnswerSource["kind"] =
            row.kind === "paper" || row.kind === "official" ? row.kind : "other";
          const provider = asProvider(row.provider);
          return {
            title: String(row.title || "").trim(),
            url: String(row.url || "").trim(),
            kind,
            ...(provider ? { provider } : {}),
          };
        })
        .filter((source) => source.title && source.url.startsWith("http"))
    : [];
  const review_status = asReviewStatus(
    (data as { review_status?: unknown }).review_status,
  );
  const decisionRaw = (data as { decision?: unknown }).decision;
  const decision =
    decisionRaw === "lesson_only" || decisionRaw === "blend" || decisionRaw === "abstain"
      ? decisionRaw
      : undefined;
  const outside_lane_empty =
    (data as { outside_lane_empty?: unknown }).outside_lane_empty === true;
  const web_search = asWebSearch((data as { web_search?: unknown }).web_search);
  return {
    v: 1,
    lesson,
    external,
    sources,
    ...(review_status ? { review_status } : {}),
    ...(decision ? { decision } : {}),
    ...(outside_lane_empty ? { outside_lane_empty: true } : {}),
    ...(web_search ? { web_search } : {}),
  };
}

function stringList(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .slice(0, limit);
}

function asWebSearch(value: unknown): WebSearchPlan | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Partial<WebSearchPlan>;
  const queries = stringList(row.queries, 4);
  const keywords = stringList(row.keywords, 8);
  if (queries.length === 0 && keywords.length === 0) return undefined;
  const score = Number(row.score);
  return {
    queries,
    keywords,
    score: Number.isFinite(score) ? Math.max(0, Math.min(100, Math.round(score))) : 0,
    accepted: row.accepted === true,
    note: String(row.note || "").trim().slice(0, 240),
  };
}

function asReviewStatus(value: unknown): ReviewStatus | undefined {
  if (value === "accepted" || value === "regenerated" || value === "withheld") return value;
  return undefined;
}

export function parseTutorAnswer(content: string): TutorAnswer | null {
  const trimmed = content.trim();
  if (!trimmed.startsWith("{")) return null;
  try {
    return asTutorAnswer(JSON.parse(trimmed));
  } catch {
    return null;
  }
}

export function hostLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
