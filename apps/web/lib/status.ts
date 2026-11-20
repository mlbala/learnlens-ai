/**
 * Central status → label / tone mapping (docs/07_UI_UX_DESIGN_SYSTEM.md §7).
 * Fixture-safe; no invented coverage claims.
 */

export type SourceStatus =
  | "needs_transcript"
  | "queued"
  | "processing"
  | "validating"
  | "normalizing"
  | "segmenting"
  | "summarizing"
  | "indexing"
  | "ready"
  | "failed_retryable"
  | "failed_terminal"
  | "not_authorized"
  | "unavailable"
  | "metadata_only"
  | "discovered"
  | "deleted";

export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info";

export type StatusPresentation = {
  label: string;
  tone: StatusTone;
  actionHint?: string;
};

const PROCESSING_STAGES: ReadonlySet<SourceStatus> = new Set([
  "queued",
  "processing",
  "validating",
  "normalizing",
  "segmenting",
  "summarizing",
  "indexing",
]);

export function isProcessingStatus(status: string): boolean {
  return PROCESSING_STAGES.has(status as SourceStatus);
}

export function presentStatus(status: string): StatusPresentation {
  switch (status) {
    case "needs_transcript":
    case "metadata_only":
      return {
        label: "Transcript needed",
        tone: "warning",
        actionHint: "Add transcript",
      };
    case "queued":
    case "processing":
    case "validating":
    case "normalizing":
    case "segmenting":
    case "summarizing":
    case "indexing":
      return { label: "Processing", tone: "neutral" };
    case "ready":
      return { label: "Ready to study", tone: "success" };
    case "failed_retryable":
      return {
        label: "Processing interrupted",
        tone: "danger",
        actionHint: "Retry",
      };
    case "failed_terminal":
      return { label: "Processing failed", tone: "danger" };
    case "not_authorized":
      return { label: "Permission required", tone: "warning" };
    case "unavailable":
      return { label: "Video unavailable", tone: "neutral" };
    case "discovered":
      return { label: "Discovered", tone: "info" };
    case "deleted":
      return { label: "Deleted", tone: "neutral" };
    case "partial":
      return {
        label: "Partial coverage",
        tone: "warning",
        actionHint: "Add missing transcripts",
      };
    case "fixture":
      return { label: "Fixture data", tone: "info" };
    case "failed":
      return {
        label: "Processing interrupted",
        tone: "danger",
        actionHint: "Retry",
      };
    default:
      return { label: "Unknown status", tone: "neutral" };
  }
}

/** Honest playlist coverage copy — never invents missing video content. */
export function playlistCoverageLabel(ready: number, total: number): string {
  if (!Number.isFinite(ready) || !Number.isFinite(total) || total < 0 || ready < 0) {
    return "Coverage unavailable";
  }
  if (total === 0) {
    return "No videos in playlist";
  }
  if (ready >= total) {
    return `Summary covers ${total} of ${total} videos`;
  }
  return `Summary covers ${ready} of ${total} videos`;
}
