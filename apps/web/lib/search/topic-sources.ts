export type TopicSource = {
  title: string;
  url: string;
  snippet: string;
  kind: "paper" | "official" | "other";
  provider?: "tavily" | "semantic_scholar" | "openalex";
};

const ACADEMIC =
  /(arxiv\.org|semanticscholar\.org|doi\.org|acm\.org|ieeexplore|ieee\.org|nature\.com|science\.org|springer\.com|nih\.gov|pubmed|openalex\.org|ssrn\.com|acm\.dl)/i;
const OFFICIAL =
  /(^https?:\/\/docs\.|\/docs\/|developer\.|readthedocs\.io|github\.io|rfc-editor\.org|w3\.org|learn\.microsoft\.com|cloud\.google\.com|ai\.google\.dev|platform\.openai\.com|docs\.python\.org|kubernetes\.io|pytorch\.org|tensorflow\.org|huggingface\.co\/docs|nodejs\.org|developer\.mozilla|mdn\.|spec\.|documentation)/i;

function runtimeEnv(name: string): string {
  return (process.env[name] ?? "").trim();
}

export function sourceKind(url: string): TopicSource["kind"] {
  if (ACADEMIC.test(url)) return "paper";
  if (OFFICIAL.test(url)) return "official";
  return "other";
}

export function rankTopicSources(sources: TopicSource[]): TopicSource[] {
  const seen = new Set<string>();
  const unique = sources.filter((source) => {
    const key = source.url.replace(/\/$/, "").toLowerCase();
    if (!source.title || !source.url || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const weight = { paper: 0, official: 1, other: 2 };
  const sorted = unique.sort((a, b) => weight[a.kind] - weight[b.kind]);
  const preferred = sorted.filter((source) => source.kind !== "other");
  const extras =
    preferred.length >= 3 ? [] : sorted.filter((source) => source.kind === "other").slice(0, 3 - preferred.length);
  return [...preferred, ...extras].slice(0, 6);
}

function openAlexAbstract(index: Record<string, number[]> | null | undefined): string {
  if (!index) return "";
  const words: string[] = [];
  for (const [word, positions] of Object.entries(index)) {
    for (const position of positions) words[position] = word;
  }
  return words.filter(Boolean).join(" ").slice(0, 480);
}

async function semanticScholar(query: string): Promise<TopicSource[]> {
  const url =
    "https://api.semanticscholar.org/graph/v1/paper/search?limit=4&fields=title,abstract,url,externalIds&query=" +
    encodeURIComponent(query);
  const res = await fetch(url, {
    headers: { accept: "application/json", "user-agent": "LearnLens/0.1 (lesson search)" },
    signal: AbortSignal.timeout(12_000),
  });
  if (!res.ok) return [];
  const body = (await res.json().catch(() => null)) as {
    data?: { title?: string; abstract?: string; url?: string; externalIds?: { DOI?: string } }[];
  } | null;
  return (body?.data ?? []).map((paper) => {
    const doi = paper.externalIds?.DOI;
    const link = paper.url || (doi ? `https://doi.org/${doi}` : "");
    return {
      title: paper.title || "Untitled paper",
      url: link,
      snippet: (paper.abstract || "").slice(0, 480),
      kind: "paper" as const,
      provider: "semantic_scholar" as const,
    };
  }).filter((paper) => paper.url);
}

async function openAlex(query: string): Promise<TopicSource[]> {
  const url =
    "https://api.openalex.org/works?per-page=4&select=display_name,abstract_inverted_index,doi,id&search=" +
    encodeURIComponent(query);
  const res = await fetch(url, {
    headers: { accept: "application/json", "user-agent": "LearnLens/0.1 (lesson search)" },
    signal: AbortSignal.timeout(12_000),
  });
  if (!res.ok) return [];
  const body = (await res.json().catch(() => null)) as {
    results?: { display_name?: string; abstract_inverted_index?: Record<string, number[]>; doi?: string; id?: string }[];
  } | null;
  return (body?.results ?? []).map((work) => ({
    title: work.display_name || "Untitled paper",
    url: work.doi || work.id || "",
    snippet: openAlexAbstract(work.abstract_inverted_index),
    kind: "paper" as const,
    provider: "openalex" as const,
  })).filter((work) => work.url);
}

async function tavily(query: string, apiKey: string): Promise<TopicSource[]> {
  const res = await fetch("https://api.tavily.com/search", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey,
      query: `${query} academic paper OR official documentation OR specification`,
      search_depth: "basic",
      max_results: 6,
      include_answer: false,
    }),
    signal: AbortSignal.timeout(12_000),
  });
  if (!res.ok) return [];
  const body = (await res.json().catch(() => null)) as {
    results?: { title?: string; url?: string; content?: string }[];
  } | null;
  return (body?.results ?? []).map((result) => ({
    title: result.title || result.url || "Source",
    url: result.url || "",
    snippet: (result.content || "").slice(0, 480),
    kind: sourceKind(result.url || ""),
    provider: "tavily" as const,
  })).filter((result) => result.url);
}

export async function searchTopicSources(query: string): Promise<TopicSource[]> {
  const tavilyKey = runtimeEnv("TAVILY_API_KEY");
  const tasks = [semanticScholar(query), openAlex(query)];
  if (tavilyKey) tasks.unshift(tavily(query, tavilyKey));
  const batches = await Promise.all(tasks.map((task) => task.catch(() => [] as TopicSource[])));
  return rankTopicSources(batches.flat());
}

export function formatTopicSources(sources: TopicSource[]): string {
  if (sources.length === 0) return "";
  return sources
    .map((source, index) => {
      const label = source.kind === "paper" ? "academic paper" : source.kind === "official" ? "official documentation" : "web page";
      return `SOURCE ${index + 1} (${label})\nTitle: ${source.title}\nURL: ${source.url}\nExcerpt: ${source.snippet || "(no excerpt)"}`;
    })
    .join("\n\n");
}
