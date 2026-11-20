"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  citationLabel,
  citationOpenUrl,
  citationSeekSeconds,
  citationTimingHint,
  formatClock,
} from "@/lib/lesson/citations";
import type { Citation } from "@/lib/lesson/types";
import { cn } from "@/lib/utils";

type EvidenceCitationProps = {
  citation: Citation;
  youtubeVideoId?: string | null;
  onSeek?: (seconds: number) => void;
  className?: string;
};

/** Server-supplied citation chip — timed jumps only when timing_verified. */
export function EvidenceCitation({
  citation,
  youtubeVideoId,
  onSeek,
  className,
}: EvidenceCitationProps) {
  const seconds = citationSeekSeconds(citation);
  const openUrl = citationOpenUrl(citation, youtubeVideoId);
  const timed = seconds != null;

  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-[var(--radius-control)] border border-border bg-surface-muted/60 px-2.5 py-2",
        className,
      )}
      data-testid={`citation-${citation.citation_id}`}
      data-timing-verified={citation.timing_verified ? "true" : "false"}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={timed ? "info" : "secondary"}>{citationLabel(citation)}</Badge>
        <span className="text-xs text-muted-foreground">{citationTimingHint(citation)}</span>
      </div>
      <p className="text-xs leading-relaxed text-foreground">{citation.snippet}</p>
      <div className="flex flex-wrap gap-2">
        {timed ? (
          <Button
            type="button"
            size="sm"
            variant="default"
            onClick={() => onSeek?.(seconds)}
            aria-label={`Jump in player at ${formatClock(seconds)}`}
          >
            Jump in player
          </Button>
        ) : null}
        {openUrl ? (
          <Button asChild size="sm" variant="outline">
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={
                timed
                  ? `Open source at ${formatClock(seconds)}`
                  : "Open source without exact time"
              }
            >
              {timed ? "Open at time" : "Open source"}
            </a>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
