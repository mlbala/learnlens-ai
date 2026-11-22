import type { AnswerSource } from "@/lib/lesson/answer";
import type { ExplanationMode } from "@/lib/lesson/types";

const FOLLOWUP_RULE =
  'When the learner says "explain that", "give an example", or "why", that refers to the previous lesson panel. It does not refer to an earlier paper summary.';

export const VIDEO_DOES_NOT_COVER = "The video does not cover this question.";

export type PromptEvidence = {
  id: string;
  evidence_origin: "video_transcript" | "external_search";
  text: string;
};

export function buildLessonModelPrompt(input: {
  title?: string;
  transcript: string;
  question: string;
  explanationMode?: ExplanationMode | string;
  externalSearch: boolean;
  packedHistory?: string;
  sources: AnswerSource[];
  evidence?: PromptEvidence[];
}): string {
  const detailed = input.explanationMode !== "simple";
  const depth = detailed
    ? "lesson must contain four sections titled exactly What it is, How it works, Example, and Watch-outs. Each body is one clear paragraph of plain prose."
    : "lesson must contain one section titled Answer. The body is one or two plain paragraphs.";
  const ordered = orderedEvidence(input.evidence, input.externalSearch);
  const usingEvidence = input.evidence !== undefined;
  const sourceBlock =
    usingEvidence || !input.externalSearch ? "" : formatSources(input.sources);
  const hasExternal = usingEvidence
    ? ordered.some((block) => block.evidence_origin === "external_search")
    : Boolean(sourceBlock);
  const external = hasExternal
    ? usingEvidence
      ? "external must contain the same kind of sections, using only the blocks labeled external_search. Prefer academic papers and official documentation. Do not mention source numbers."
      : "external must contain the same kind of sections, using only the SOURCE excerpts. Prefer academic papers and official documentation. Do not mention source numbers."
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
  ];
  if (usingEvidence) {
    parts.push(`EVIDENCE:\n${formatEvidence(ordered)}`);
  } else {
    parts.push(`LESSON:\n${input.transcript}`);
  }
  if (memory) parts.push(`FOLLOW-UP MEMORY:\n${memory}`);
  if (sourceBlock) parts.push(`SOURCES:\n${sourceBlock}`);
  parts.push(`QUESTION:\n${input.question}`);
  return parts.join("\n\n");
}

function orderedEvidence(evidence: PromptEvidence[] | undefined, externalSearch: boolean): PromptEvidence[] {
  const rows = evidence ?? [];
  const video = rows.filter((block) => block.evidence_origin === "video_transcript" && block.text.trim());
  const external = externalSearch
    ? rows.filter((block) => block.evidence_origin === "external_search" && block.text.trim())
    : [];
  return [...video, ...external];
}

function formatEvidence(blocks: PromptEvidence[]): string {
  if (blocks.length === 0) return "(none)";
  return blocks
    .map((block) => `BLOCK ${block.evidence_origin} id=${block.id}\n${block.text.trim()}`)
    .join("\n\n");
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
