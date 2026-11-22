import { describe, expect, it } from "vitest";

import { noteParagraphs, recoverLessonFields } from "@/lib/lesson/notes";

const TRUNCATED = `{
  "title": "Agents",
  "summary": "Agents plan, act, and check their work. Memory keeps the next step. Evals show whether the loop helped.",
  "key_points": [
    "Agents plan before they act.",
    "Memory keeps the next step.",
    "Evals are cut off mid sent
`;

describe("recoverLessonFields", () => {
  it("reads a finished summary and complete points out of a cut-off JSON blob", () => {
    const notes = recoverLessonFields({ summary: TRUNCATED, transcript: TRUNCATED, key_points: [] });
    expect(notes.summary).toContain("Agents plan, act, and check");
    expect(notes.keyPoints).toEqual(["Agents plan before they act.", "Memory keeps the next step."]);
    expect(notes.transcript.startsWith("{")).toBe(false);
    expect(notes.transcript).toContain("Memory keeps the next step.");
  });

  it("leaves plain notes alone", () => {
    const notes = recoverLessonFields({
      summary: "A short overview of the lesson.",
      key_points: ["One complete point about the lesson."],
      transcript: "Spoken line.",
    });
    expect(notes.summary).toBe("A short overview of the lesson.");
    expect(notes.keyPoints).toEqual(["One complete point about the lesson."]);
    expect(notes.transcript).toBe("Spoken line.");
  });

  it("splits a long overview into paragraphs", () => {
    const paragraphs = noteParagraphs(
      "First sentence stays with the second. Second sentence ends the pair. Third sentence opens the next pair. Fourth sentence closes it.",
    );
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]).toContain("First sentence");
    expect(paragraphs[1]).toContain("Fourth sentence");
  });
});
