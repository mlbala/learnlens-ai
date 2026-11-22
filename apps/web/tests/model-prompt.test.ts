import { describe, expect, it } from "vitest";

import { buildLessonModelPrompt } from "@/lib/lesson/model-prompt";

const packed =
  "Lesson panel (video_transcript):\nWhat it is: LESSON_MARK\nOutside panel (external_search):\nPAPER_MARK";

describe("buildLessonModelPrompt", () => {
  it("sends packed lesson memory and leaves current paper text out when search is off", () => {
    const prompt = buildLessonModelPrompt({
      title: "Agents",
      transcript: "The loop repeats.",
      question: "explain that",
      explanationMode: "standard",
      externalSearch: false,
      packedHistory: packed,
      sources: [
        {
          title: "Paper",
          url: "https://doi.org/10.1/new",
          kind: "paper",
          provider: "semantic_scholar",
        },
      ],
    });
    expect(prompt).toContain("FOLLOW-UP MEMORY:");
    expect(prompt).toContain("LESSON_MARK");
    expect(prompt).toContain("video_transcript");
    expect(prompt).toContain("explain that");
    expect(prompt).toContain("The loop repeats.");
    expect(prompt).not.toContain("SOURCES:");
    expect(prompt).not.toContain("doi.org");
  });

  it("labels earlier outside text and the current search when the checkbox is on", () => {
    const prompt = buildLessonModelPrompt({
      transcript: "The loop repeats.",
      question: "why",
      externalSearch: true,
      packedHistory: packed,
      sources: [
        {
          title: "Paper",
          url: "https://doi.org/10.1/new",
          kind: "paper",
          provider: "openalex",
        },
      ],
    });
    expect(prompt).toContain("PAPER_MARK");
    expect(prompt).toContain("external_search");
    expect(prompt).toContain("https://doi.org/10.1/new");
    expect(prompt).toContain("openalex");
    expect(prompt).toContain("why");
  });

  it("puts the video block before outside text and leaves the full transcript out", () => {
    const prompt = buildLessonModelPrompt({
      transcript: "FULL_TRANSCRIPT_SHOULD_STAY_OUT",
      question: "How do leaves capture sunlight?",
      externalSearch: true,
      evidence: [
        {
          id: "video-1",
          evidence_origin: "video_transcript",
          text: "Leaves capture sunlight.",
        },
        {
          id: "paper-1",
          evidence_origin: "external_search",
          text: "OUTSIDE_SNIPPET_ONLY",
        },
      ],
      sources: [],
    });
    const videoAt = prompt.indexOf("BLOCK video_transcript");
    const outsideAt = prompt.indexOf("BLOCK external_search");
    expect(videoAt).toBeGreaterThan(-1);
    expect(outsideAt).toBeGreaterThan(videoAt);
    expect(prompt.slice(0, outsideAt)).not.toContain("OUTSIDE_SNIPPET_ONLY");
    expect(prompt).toContain("Leaves capture sunlight.");
    expect(prompt).not.toContain("FULL_TRANSCRIPT_SHOULD_STAY_OUT");
    expect(prompt).not.toContain("score");
  });
});
