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

export type TutorAnswer = {
  v: 1;
  lesson: AnswerSection[];
  external: AnswerSection[];
  sources: AnswerSource[];
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
  return { v: 1, lesson, external, sources };
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
