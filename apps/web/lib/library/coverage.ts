import type { PlaylistCoverage } from "@/lib/library/types";
import { playlistCoverageLabel } from "@/lib/status";

const EMPTY: PlaylistCoverage = {
  total: 0,
  ready: 0,
  needs_transcript: 0,
  unavailable: 0,
  failed: 0,
  missing: 0,
};

/** Normalize API coverage dict; never invents ready counts. */
export function normalizeCoverage(
  raw: Partial<PlaylistCoverage> | Record<string, number> | null | undefined,
  fallbackTotal = 0,
): PlaylistCoverage {
  if (!raw || typeof raw !== "object") {
    return { ...EMPTY, total: Math.max(0, fallbackTotal), missing: Math.max(0, fallbackTotal) };
  }
  const total = nonNeg(raw.total ?? fallbackTotal);
  const ready = nonNeg(raw.ready);
  const needs_transcript = nonNeg(raw.needs_transcript);
  const unavailable = nonNeg(raw.unavailable);
  const failed = nonNeg(raw.failed);
  const missing =
    typeof raw.missing === "number"
      ? nonNeg(raw.missing)
      : Math.max(0, total - ready);
  return { total, ready, needs_transcript, unavailable, failed, missing };
}

function nonNeg(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.floor(n);
}

/** True when any source limitation prevents claiming full coverage. */
export function isPartialCoverage(coverage: PlaylistCoverage): boolean {
  if (coverage.total <= 0) return false;
  return (
    coverage.ready < coverage.total ||
    coverage.unavailable > 0 ||
    coverage.failed > 0 ||
    coverage.needs_transcript > 0
  );
}

/** Progress fraction from ready/total — UI must still show partial when sources are limited. */
export function coverageReadyFraction(coverage: PlaylistCoverage): number {
  if (coverage.total <= 0) return 0;
  return Math.min(coverage.ready, coverage.total) / coverage.total;
}

/** Display percent — never shows 100 when unavailable/failed items remain. */
export function coverageDisplayPercent(coverage: PlaylistCoverage): number {
  if (coverage.total <= 0) return 0;
  if (coverage.unavailable > 0 || coverage.failed > 0) {
    const max = Math.floor(((coverage.total - 1) / coverage.total) * 100);
    return Math.min(Math.round(coverageReadyFraction(coverage) * 100), max);
  }
  return Math.round(coverageReadyFraction(coverage) * 100);
}

export function coverageHeadline(coverage: PlaylistCoverage): string {
  if (coverage.total <= 0) return "No videos in playlist";
  return `${coverage.ready} of ${coverage.total} ready`;
}

export function coverageLimitationCopy(coverage: PlaylistCoverage): string {
  if (coverage.total <= 0) {
    return "Import a playlist to see coverage. A URL alone never grants transcript access.";
  }
  const parts: string[] = [];
  if (coverage.needs_transcript > 0) {
    parts.push(`${coverage.needs_transcript} need a permitted transcript`);
  }
  if (coverage.unavailable > 0) {
    parts.push(`${coverage.unavailable} unavailable`);
  }
  if (coverage.failed > 0) {
    parts.push(`${coverage.failed} failed`);
  }
  if (parts.length === 0) {
    return playlistCoverageLabel(coverage.ready, coverage.total);
  }
  const base = playlistCoverageLabel(coverage.ready, coverage.total);
  return `${base}. Source limitations: ${parts.join(", ")}.`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—";
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rem = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(rem).padStart(2, "0")}`;
  return `${m}:${String(rem).padStart(2, "0")}`;
}
