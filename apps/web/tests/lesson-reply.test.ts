// @vitest-environment node
import { describe, expect, it } from "vitest";

import { LESSON_PROMPT, parseLessonJson, readLesson } from "@/lib/lesson/lesson-reply";
import { proposeSearchTerms } from "@/lib/search/search-plan";

const FULL = JSON.stringify({
  title: "Sovereign AI",
  summary: "Sovereign AI keeps an organization in control of its AI lifecycle.",
  key_points: ["Data residency and compliance are central to sovereign AI."],
  transcript: "The appetite for AI across teams is large.\n\nSovereign AI means control from data to inference.",
});

describe("lesson build prompt", () => {
  it("asks for the whole transcript, last, without summarizing", () => {
    expect(LESSON_PROMPT).toContain("title, summary, key_points, transcript");
    expect(LESSON_PROMPT).toContain("from the first word to the last");
    expect(LESSON_PROMPT).toContain("Do not summarize, skip sections, or stop early.");
  });
});

describe("lesson reply", () => {
  it("reads a complete reply", () => {
    const lesson = readLesson(FULL);
    expect(lesson?.title).toBe("Sovereign AI");
    expect(lesson?.transcript).toContain("control from data to inference");
  });

  it("keeps a reply cut at the output limit inside the transcript", () => {
    const cut = FULL.slice(0, FULL.indexOf("Sovereign AI means") + 12);
    const lesson = readLesson(cut, "MAX_TOKENS");
    expect(lesson?.summary).toContain("in control of its AI lifecycle");
    expect(lesson?.key_points).toHaveLength(1);
    expect(lesson?.transcript.endsWith("Sovereign AI")).toBe(true);
  });

  it("does not patch broken JSON when the model finished normally", () => {
    expect(() => parseLessonJson('{"title": "x", "transcript": "cut', "STOP")).toThrow();
  });
});

describe("search terms from spoken text", () => {
  it("does not pad the query with filler words", () => {
    const { queries, keywords } = proposeSearchTerms({
      title: "Sovereign AI",
      summary:
        "New technology comes out, one team gets it to work, then another team, and another, and pretty soon you have an ecosystem. One team, another team.",
      question: "what is concept of sovereign ai",
    });
    for (const filler of ["one", "another", "have", "pretty", "soon"]) {
      expect(keywords).not.toContain(filler);
      expect(queries[0]?.split(" ").slice(6) ?? []).not.toContain(filler);
    }
  });
});
