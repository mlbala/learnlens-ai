import type { AnswerSource } from "@/lib/lesson/answer";
import type { ExplanationMode } from "@/lib/lesson/types";

const FOLLOWUP_RULE =
  'When the learner says "explain that", "give an example", or "why", that refers to the previous lesson panel. It does not refer to an earlier paper summary.';

export function buildLessonModelPrompt(input: {
  title?: string;
  transcript: string;
  question: string;
  explanationMode?: ExplanationMode | string;
  externalSearch: boolean;
  packedHistory?: string;
  sources: AnswerSource[];
}): string {
  const detailed = input.explanationMode !== "simple";
  const depth = detailed
    ? "lesson must contain four sections titled exactly What it is, How it works, Example, and Watch-outs. Each body is one clear paragraph of plain prose."
    : "lesson must contain one section titled Answer. The body is one or two plain paragraphs.";
  const sourceBlock = formatSources(input.externalSearch ? input.sources : []);
  const external = sourceBlock
    ? "external must contain the same kind of sections, using only the SOURCE excerpts. Prefer academic papers and official documentation. Do not mention source numbers."
    : "external must be an empty array.";
  const memory = input.packedHistory?.trim() || "";
  const parts = [
    "Return JSON only with keys lesson and external. Each is an array of objects with heading and body. " +
      `${depth} ${external} No markdown, no URLs, no timestamps.`,
    FOLLOWUP_RULE,
    "Lesson blocks labeled video_transcript are the video. Blocks labeled external_search are not the video.",
    input.externalSearch
      ? "The live search checkbox is on for this question only. Do not search earlier questions again."
      : "The live search checkbox is off. Answer from the lesson panel. Do not use an earlier paper summary.",
    `VIDEO: ${input.title || "the video"}`,
    `LESSON:\n${input.transcript}`,
  ];
  if (memory) parts.push(`FOLLOW-UP MEMORY:\n${memory}`);
  if (sourceBlock) parts.push(`SOURCES:\n${sourceBlock}`);
  parts.push(`QUESTION:\n${input.question}`);
  return parts.join("\n\n");
}

function formatSources(sources: AnswerSource[]): string {
  if (sources.length === 0) return "";
  return sources
    .map((source, index) => {
      const provider = source.provider || "source";
      return `SOURCE ${index + 1} (${provider})\nTitle: ${source.title}\nURL: ${source.url}`;
    })
    .join("\n\n");
}
