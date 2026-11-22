import { describe, expect, it } from "vitest";

import { rankTopicSources, sourceKind } from "@/lib/search/topic-sources";

describe("topic source ranking", () => {
  it("prefers papers and official docs over general pages", () => {
    const ranked = rankTopicSources([
      { title: "Blog", url: "https://example.com/post", snippet: "a", kind: "other" },
      { title: "Docs", url: "https://docs.example.com/guide", snippet: "b", kind: sourceKind("https://docs.example.com/guide") },
      { title: "Paper", url: "https://arxiv.org/abs/1", snippet: "c", kind: "paper" },
      { title: "Paper again", url: "https://arxiv.org/abs/1/", snippet: "c", kind: "paper" },
    ]);
    expect(ranked.map((source) => source.title)).toEqual(["Paper", "Docs", "Blog"]);
    const crowded = rankTopicSources([
      ...ranked,
      { title: "Second paper", url: "https://doi.org/10.1/abc", snippet: "d", kind: "paper" },
    ]);
    expect(crowded.map((source) => source.title)).toEqual(["Paper", "Second paper", "Docs"]);
    expect(sourceKind("https://pytorch.org/docs/stable")).toBe("official");
  });
});
