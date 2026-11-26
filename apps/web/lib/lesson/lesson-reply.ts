import { recoverLessonFields } from "@/lib/lesson/notes";
import { toLessonTitle } from "@/lib/lesson/title";

/**
 * The transcript is what questions are answered from, so it must cover the whole video,
 * not the opening minute or a list of highlights. It is the last key so a reply cut at
 * the output limit still parses.
 */
export const LESSON_PROMPT =
  "Watch this public YouTube video. Return JSON with keys in this order: title, summary, key_points, transcript. " +
  "Title is a short plain name with no emoji, hashtags, or decoration. " +
  "Summary is two or three short paragraphs of plain sentences. " +
  "key_points is up to 6 complete sentences. " +
  "transcript is everything said in the video from the first word to the last, close to word for word, " +
  "in paragraphs of three to six sentences separated by a blank line. Do not summarize, skip sections, or stop early. " +
  "If the video is longer than about 45 minutes, keep every topic in order and shorten the wording instead of leaving parts out. " +
  "Do not invent timestamps. If you cannot access the video, set summary and transcript to empty strings.";

export type LessonPayload = {
  title?: string;
  summary?: string;
  key_points?: string[];
  transcript?: string;
};

export type BuiltLesson = {
  title: string;
  summary: string;
  key_points: string[];
  transcript: string;
};

/**
 * JSON from a reply that stopped at the output limit. The transcript is the last key,
 * so closing its string keeps the title, summary, key points, and the transcript so far.
 */
export function parseLessonJson(text: string, finish: string): unknown {
  try {
    return JSON.parse(text);
  } catch (error) {
    if (finish !== "MAX_TOKENS") throw error;
    const body = text.trimEnd().replace(/\\+$/, "");
    for (const ending of ['"}', '"]}', "}", "]}"]) {
      try {
        return JSON.parse(body + ending);
      } catch {
        // Try the next way to close it.
      }
    }
    throw error;
  }
}

/** The lesson fields from one model reply, or null when the model could not read the video. */
export function readLesson(text: string, finish = "STOP"): BuiltLesson | null {
  let parsed: LessonPayload = {};
  try {
    const value: unknown = parseLessonJson(text, finish);
    // Some Flash-Lite models wrap the object in an array: [{ "title": ... }].
    const object = Array.isArray(value) ? value.find((item) => item && typeof item === "object") : value;
    parsed = (object && typeof object === "object" ? object : {}) as LessonPayload;
  } catch {
    parsed = { summary: text, transcript: text, key_points: [] };
  }
  const lesson = recoverLessonFields({
    summary: parsed.summary || "",
    key_points: parsed.key_points,
    transcript: parsed.transcript,
  });
  if (!lesson.summary && !lesson.transcript) return null;
  return {
    title: toLessonTitle(parsed.title || ""),
    summary: lesson.summary || "",
    key_points: lesson.keyPoints,
    transcript: lesson.transcript || lesson.summary || "",
  };
}
