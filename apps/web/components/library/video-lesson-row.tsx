import Link from "next/link";

import { SourceStatusBadge } from "@/components/patterns/source-status-badge";
import { formatDuration } from "@/lib/library/coverage";
import type { PlaylistItemRecord } from "@/lib/library/types";
import { cn } from "@/lib/utils";

type VideoLessonRowProps = {
  item: PlaylistItemRecord;
  className?: string;
};

export function VideoLessonRow({ item, className }: VideoLessonRowProps) {
  const href = item.video_id ? `/videos/${item.video_id}` : undefined;
  const title = item.title?.trim() || `Video ${item.youtube_video_id}`;
  const content = (
    <>
      <span className="w-8 shrink-0 tabular-nums text-muted-foreground">
        {item.playlist_position + 1}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium text-foreground">{title}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {item.channel_title ?? "Channel unavailable"} ·{" "}
          {formatDuration(item.duration_seconds)}
        </span>
      </span>
      <SourceStatusBadge status={item.state === "failed" ? "failed_retryable" : item.state} />
    </>
  );

  const classes = cn(
    "flex min-h-11 items-center gap-3 rounded-[var(--radius-control)] border border-border bg-surface px-3 py-2 text-sm",
    href && "transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    className,
  );

  if (href) {
    return (
      <Link href={href} className={classes} aria-label={`Open ${title}`}>
        {content}
      </Link>
    );
  }

  return (
    <div className={classes} aria-label={title}>
      {content}
    </div>
  );
}
