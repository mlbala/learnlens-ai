import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  coverageDisplayPercent,
  coverageHeadline,
  coverageLimitationCopy,
  isPartialCoverage,
} from "@/lib/library/coverage";
import type { PlaylistCoverage } from "@/lib/library/types";
import { cn } from "@/lib/utils";

type PlaylistCoverageProps = {
  coverage: PlaylistCoverage;
  className?: string;
  compact?: boolean;
};

export function PlaylistCoverageBar({
  coverage,
  className,
  compact = false,
}: PlaylistCoverageProps) {
  const partial = isPartialCoverage(coverage);
  const percent = coverageDisplayPercent(coverage);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-foreground">
          {coverageHeadline(coverage)}
        </p>
        {partial ? (
          <Badge variant="warning" aria-label="Partial coverage">
            Partial
          </Badge>
        ) : null}
        {coverage.unavailable > 0 ? (
          <Badge variant="secondary">Source limited</Badge>
        ) : null}
      </div>
      <Progress
        value={percent}
        label={`Playlist coverage ${coverage.ready} of ${coverage.total} ready`}
      />
      {!compact ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>
            Ready {coverage.ready}/{coverage.total}
          </span>
          <span>Missing {coverage.missing}</span>
          <span>Needs transcript {coverage.needs_transcript}</span>
          <span>Unavailable {coverage.unavailable}</span>
          <span>Failed {coverage.failed}</span>
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">{coverageLimitationCopy(coverage)}</p>
    </div>
  );
}
