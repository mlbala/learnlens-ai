export type RecoveredLesson = {
  summary: string;
  keyPoints: string[];
  transcript: string;
};

function unescapeJson(value: string): string {
  return value.replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\\/g, "\\").trim();
}

function looksLikeLessonJson(text: string): boolean {
  const trimmed = text.trim();
  return trimmed.startsWith("{") && trimmed.includes('"summary"');
}

function stringField(text: string, key: string): string {
  const match = text.match(new RegExp(`"${key}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`));
  return match?.[1] ? unescapeJson(match[1]) : "";
}

function completeStrings(text: string, key: string): string[] {
  const match = text.match(new RegExp(`"${key}"\\s*:\\s*\\[([\\s\\S]*)`));
  if (!match?.[1]) return [];
  const body = match[1];
  const items: string[] = [];
  const pattern = /"((?:\\.|[^"\\])*)"/g;
  let found: RegExpExecArray | null;
  while ((found = pattern.exec(body))) {
    const value = found[1] ? unescapeJson(found[1]) : "";
    const after = body.slice(found.index + found[0].length).trimStart();
    if (value && (after.startsWith(",") || after.startsWith("]"))) items.push(value);
  }
  return items;
}

export function recoverLessonFields(raw?: {
  summary?: string;
  key_points?: string[];
  transcript?: string;
} | null): RecoveredLesson {
  const summaryRaw = raw?.summary || "";
  const transcriptRaw = (raw?.transcript || "").trim();
  const packed = looksLikeLessonJson(summaryRaw)
    ? summaryRaw
    : looksLikeLessonJson(transcriptRaw)
      ? transcriptRaw
      : "";
  const summary = (packed ? stringField(packed, "summary") : summaryRaw).trim();
  const extractedPoints = packed ? completeStrings(packed, "key_points") : [];
  const keyPoints = (extractedPoints.length > 0 ? extractedPoints : raw?.key_points || [])
    .map((point) => point.trim())
    .filter((point) => point.length >= 12)
    .slice(0, 8);
  const extractedTranscript = packed ? stringField(packed, "transcript") : "";
  const transcriptBroken = looksLikeLessonJson(transcriptRaw) || transcriptRaw.includes('"key_points"');
  const transcript =
    extractedTranscript ||
    (!transcriptBroken ? transcriptRaw : "") ||
    [summary, ...keyPoints].filter(Boolean).join("\n\n");
  return { summary, keyPoints, transcript };
}

export function noteParagraphs(summary: string): string[] {
  const blocks = summary
    .split(/\n{2,}/)
    .map((block) => block.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  if (blocks.length > 1) return blocks;
  const cleaned = blocks[0] || "";
  if (!cleaned) return [];
  const sentences = cleaned.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [
    cleaned,
  ];
  if (sentences.length <= 2) return [cleaned];
  const paragraphs: string[] = [];
  for (let index = 0; index < sentences.length; index += 2) {
    paragraphs.push(sentences.slice(index, index + 2).join(" "));
  }
  return paragraphs;
}
