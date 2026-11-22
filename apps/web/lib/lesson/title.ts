const SMALL_WORDS = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "but",
  "of",
  "for",
  "to",
  "in",
  "on",
  "at",
  "by",
  "from",
  "with",
  "as",
]);

function capitalizeWord(word: string): string {
  if (/^[A-Z0-9]{2,5}$/.test(word)) return word;
  if (/\d/.test(word) && /\p{L}/u.test(word)) return word;
  const lower = word.toLocaleLowerCase("en-US");
  return lower.replace(/(^|[-'])(\p{L})/gu, (_match, boundary: string, letter: string) => {
    return boundary + letter.toLocaleUpperCase("en-US");
  });
}

/** Plain lesson title: no emoji or decoration, title case, small words stay lower. */
export function toLessonTitle(raw: string): string {
  const cleaned = raw
    .replace(/https?:\/\/\S+/gi, " ")
    .replace(/\s+[-|]\s+youtube\s*$/i, " ")
    .replace(/\p{Extended_Pictographic}/gu, " ")
    .replace(/[|\\/*_~`#@^+=<>[\]{}!?]+/g, " ")
    .replace(/["“”«»]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[\s\-–—:.,]+|[\s\-–—:.,]+$/g, "")
    .trim();
  if (!cleaned) return "";
  const words = cleaned.split(" ");
  return words
    .map((word, index) => {
      const lower = word.toLocaleLowerCase("en-US");
      if (index > 0 && index < words.length - 1 && SMALL_WORDS.has(lower)) return lower;
      return capitalizeWord(word);
    })
    .join(" ");
}

export function displayLessonTitle(raw: string | null | undefined, fallback = "Untitled lesson"): string {
  return toLessonTitle(raw ?? "") || fallback;
}

export function lessonSubtitle(input: {
  channel?: string | null;
  duration?: string | null;
  extra?: string | null;
}): string {
  const channel = (input.channel ?? "").trim();
  const channelKnown = channel.length > 0 && !/^(unknown channel|channel unavailable)$/i.test(channel);
  const duration = (input.duration ?? "").trim();
  const durationKnown = duration.length > 0 && duration !== "—";
  const extra = (input.extra ?? "").trim();
  return [channelKnown ? channel : "", durationKnown ? duration : "", extra].filter(Boolean).join(" · ");
}
