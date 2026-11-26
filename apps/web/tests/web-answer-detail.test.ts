// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildLessonModelPrompt, externalShape } from "@/lib/lesson/model-prompt";
import { SNIPPET_CHARS, searchTopicSources } from "@/lib/search/topic-sources";

const EVIDENCE = [
  { id: "video-1", evidence_origin: "video_transcript" as const, text: "A sub-agent has its own context." },
  { id: "paper-1", evidence_origin: "external_search" as const, text: "Paper one abstract." },
  { id: "paper-2", evidence_origin: "external_search" as const, text: "Paper two abstract." },
];

describe("web panel detail in the answer prompt", () => {
  it("asks for two to four full web paragraphs that use every relevant outside block", () => {
    for (const mode of ["standard", "technical"]) {
      const prompt = buildLessonModelPrompt({
        transcript: "unused",
        question: "what are subagents",
        explanationMode: mode,
        externalSearch: true,
        evidence: EVIDENCE,
        sources: [],
      });
      expect(prompt).toContain("external must contain two to four sections");
      expect(prompt).toContain("four to six plain sentences");
      expect(prompt).toContain("Cover every one of the blocks labeled external_search that is relevant");
      expect(prompt).toContain("Use only the blocks labeled external_search.");
    }
  });

  it("keeps a brief answer's web panel to one section", () => {
    const prompt = buildLessonModelPrompt({
      transcript: "unused",
      question: "what are subagents",
      explanationMode: "simple",
      externalSearch: true,
      evidence: EVIDENCE,
      sources: [],
    });
    expect(prompt).toContain("external must contain one section.");
    expect(prompt).not.toContain("two to four sections");
  });

  it("leaves the web panel empty when no outside block was kept", () => {
    const prompt = buildLessonModelPrompt({
      transcript: "unused",
      question: "what are subagents",
      explanationMode: "standard",
      externalSearch: true,
      evidence: EVIDENCE.slice(0, 1),
      sources: [],
    });
    expect(prompt).toContain("external must be an empty array.");
  });

  it("names the excerpt basis when no evidence packet is used", () => {
    expect(externalShape(true, "the SOURCE excerpts")).toContain("Use only the SOURCE excerpts.");
  });
});

describe("web excerpt length", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("keeps up to SNIPPET_CHARS of each abstract instead of the first sentence", async () => {
    vi.stubEnv("TAVILY_API_KEY", "");
    const abstract = "word ".repeat(1_000).trim();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("semanticscholar")) {
          return Response.json({
            data: [{ title: "Sub-agents paper", abstract, url: "https://www.semanticscholar.org/paper/1" }],
          });
        }
        return Response.json({ results: [] });
      }),
    );
    const found = await searchTopicSources("subagents");
    expect(SNIPPET_CHARS).toBe(1_500);
    expect(found[0]?.snippet.length).toBe(SNIPPET_CHARS);
  });
});
