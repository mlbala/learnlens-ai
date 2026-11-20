/**
 * Citation helpers — only trust server-supplied timing and URLs.
 * Never invent timestamp links from model text.
 */

import type { Citation } from "@/lib/lesson/types";

/** Seconds to seek when timing is verified; null when no precise moment. */
export function citationSeekSeconds(citation: Citation): number | null {
  if (!citation.timing_verified) return null;
  if (citation.start_ms == null || !Number.isFinite(citation.start_ms)) return null;
  if (citation.start_ms < 0) return null;
  return Math.floor(citation.start_ms / 1000);
}

/** Human-readable label for a citation control. */
export function citationLabel(citation: Citation): string {
  const seconds = citationSeekSeconds(citation);
  if (seconds == null) {
    return citation.citation_id;
  }
  return `${citation.citation_id} · ${formatClock(seconds)}`;
}

/** Accessibility / helper copy when timing is missing. */
export function citationTimingHint(citation: Citation): string {
  if (citation.timing_verified && citationSeekSeconds(citation) != null) {
    return `Jump to ${formatClock(citationSeekSeconds(citation)!)}`;
  }
  return "Source available without exact time";
}

/**
 * Prefer server youtube_url. For verified timing without URL, build watch URL
 * only when youtubeVideoId is a real 11-char id and start_ms is known.
 * Never fabricate timed links for unverified citations.
 */
export function citationOpenUrl(
  citation: Citation,
  youtubeVideoId?: string | null,
): string | null {
  if (citation.youtube_url) {
    if (!citation.timing_verified) {
      // Strip accidental t= if server marked unverified (defensive).
      try {
        const u = new URL(citation.youtube_url);
        u.searchParams.delete("t");
        return u.toString();
      } catch {
        return citation.youtube_url;
      }
    }
    return citation.youtube_url;
  }

  const id = youtubeVideoId?.trim();
  if (!id || id.length !== 11) return null;

  const base = `https://www.youtube.com/watch?v=${encodeURIComponent(id)}`;
  const seconds = citationSeekSeconds(citation);
  if (seconds == null) return base;
  return `${base}&t=${seconds}s`;
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rem = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(rem).padStart(2, "0")}`;
  }
  return `${m}:${String(rem).padStart(2, "0")}`;
}

/** Build official embed src; startSeconds only applied when provided. */
export function youtubeEmbedSrc(
  youtubeVideoId: string,
  opts?: { startSeconds?: number | null; enableJsApi?: boolean },
): string {
  const params = new URLSearchParams();
  if (opts?.enableJsApi !== false) params.set("enablejsapi", "1");
  params.set("rel", "0");
  params.set("modestbranding", "1");
  if (
    opts?.startSeconds != null &&
    Number.isFinite(opts.startSeconds) &&
    opts.startSeconds >= 0
  ) {
    params.set("start", String(Math.floor(opts.startSeconds)));
  }
  return `https://www.youtube.com/embed/${encodeURIComponent(youtubeVideoId)}?${params.toString()}`;
}

/**
 * Real YouTube ids are 11 chars of [A-Za-z0-9_-]. LearnLens fixture ids
 * (vidPublic01, vidPrivate9, …) also match that shape, so callers must pass
 * `fixturePlaceholder` when rendering synthetic library items.
 */
export function isOfficialYoutubeId(id: string | null | undefined): boolean {
  return Boolean(id && /^[A-Za-z0-9_-]{11}$/.test(id));
}

/** Fixture youtube ids used by offline demos — never treat as live embeds. */
export function isFixtureYoutubeId(id: string | null | undefined): boolean {
  return Boolean(id && /^vid(Public|Private|Deleted|Unavail)/i.test(id));
}
