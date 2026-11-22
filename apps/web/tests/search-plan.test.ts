import { describe, expect, it } from "vitest";

import { proposeSearchTerms, validateSearchPlan } from "@/lib/search/search-plan";

const lesson = {
  title: "Agentic AI system design",
  summary:
    "The lesson covers a five-layer design for an e-commerce support agent. Architecture uses know, act, remember, and coordinate. Evaluation logs decisions and checks quality.",
  question: "How does the support agent remember context?",
};

describe("search plan", () => {
  it("builds search words from the lesson and the question", () => {
    const proposed = proposeSearchTerms(lesson);
    const plan = validateSearchPlan({ ...lesson, ...proposed });
    expect(plan.accepted).toBe(true);
    expect(plan.score).toBeGreaterThanOrEqual(60);
    expect(plan.keywords.join(" ")).toMatch(/agent|remember|support/);
    expect(plan.note).toBe("Searched academic papers and official documents.");
  });

  it("rejects generic search words that ignore the lesson", () => {
    const plan = validateSearchPlan({
      ...lesson,
      queries: ["explain this video please"],
      keywords: ["video", "explain"],
    });
    expect(plan.accepted).toBe(false);
    expect(plan.queries).toEqual([]);
    expect(plan.score).toBeLessThan(60);
    expect(plan.note).toContain("stays with the lesson");
  });
});
