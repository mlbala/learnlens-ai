import { describe, expect, it } from "vitest";

import { displayLessonTitle, lessonSubtitle, toLessonTitle } from "@/lib/lesson/title";

describe("toLessonTitle", () => {
  it("drops decoration and keeps a proper title", () => {
    expect(toLessonTitle("🔥 Me at the zoo!!!")).toBe("Me at the Zoo");
    expect(toLessonTitle("  me at the zoo  ")).toBe("Me at the Zoo");
    expect(toLessonTitle("Closed-loop security agents")).toBe("Closed-Loop Security Agents");
    expect(toLessonTitle("2,000+ Hours of Learning Agentic AI System Design in 20 Minutes")).toBe(
      "2,000 Hours of Learning Agentic AI System Design in 20 Minutes",
    );
    expect(toLessonTitle("")).toBe("");
  });

  it("keeps tokens that mix letters and digits", () => {
    expect(toLessonTitle("GPT-4o in practice")).toBe("GPT-4o in Practice");
  });

  it("falls back when nothing readable remains", () => {
    expect(displayLessonTitle("***")).toBe("Untitled lesson");
  });

  it("omits unknown channel and a missing duration", () => {
    expect(lessonSubtitle({ channel: "Unknown channel", duration: "—" })).toBe("");
    expect(lessonSubtitle({ channel: "jawed", duration: "0:19" })).toBe("jawed · 0:19");
  });
});
