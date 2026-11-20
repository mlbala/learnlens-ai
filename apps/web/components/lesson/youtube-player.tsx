"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  isFixtureYoutubeId,
  isOfficialYoutubeId,
  youtubeEmbedSrc,
} from "@/lib/lesson/citations";
import { formatDuration } from "@/lib/library/coverage";
import { cn } from "@/lib/utils";

export type SeekRequest = {
  seconds: number;
  token: number;
};

type YoutubePlayerProps = {
  youtubeVideoId: string;
  title: string;
  seekRequest?: SeekRequest | null;
  fixturePlaceholder?: boolean;
  className?: string;
};

/**
 * Official YouTube IFrame embed. Seek applies `start` on the embed URL when timing
 * is verified. Fixture / non-11-char IDs show a seekable placeholder (no fabricated media).
 */
export function YoutubePlayer({
  youtubeVideoId,
  title,
  seekRequest,
  fixturePlaceholder,
  className,
}: YoutubePlayerProps) {
  const iframeTitle = useId();
  const [appliedSeek, setAppliedSeek] = useState<number | null>(null);
  const lastToken = useRef<number | null>(null);

  const official =
    isOfficialYoutubeId(youtubeVideoId) &&
    !fixturePlaceholder &&
    !isFixtureYoutubeId(youtubeVideoId);

  useEffect(() => {
    if (!seekRequest) return;
    if (lastToken.current === seekRequest.token) return;
    lastToken.current = seekRequest.token;
    setAppliedSeek(seekRequest.seconds);
  }, [seekRequest]);

  const src = useMemo(() => {
    if (!official) return null;
    return youtubeEmbedSrc(youtubeVideoId, {
      startSeconds: appliedSeek,
      enableJsApi: true,
    });
  }, [official, youtubeVideoId, appliedSeek]);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--radius-panel)] border border-border bg-surface",
        className,
      )}
    >
      {official && src ? (
        <div className="relative aspect-video w-full bg-surface-muted">
          <iframe
            key={`${youtubeVideoId}-${appliedSeek ?? "base"}`}
            title={iframeTitle}
            aria-label={`YouTube player for ${title}`}
            className="absolute inset-0 h-full w-full"
            src={src}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      ) : (
        <div
          className="flex aspect-video flex-col items-center justify-center gap-2 bg-surface-muted px-6 text-center"
          role="img"
          aria-label={
            appliedSeek != null
              ? `Fixture player placeholder seeked to ${formatDuration(appliedSeek)}`
              : "Official embed unavailable for this item"
          }
        >
          <p className="text-sm font-medium text-foreground">
            {fixturePlaceholder || isFixtureYoutubeId(youtubeVideoId)
              ? "Fixture player placeholder"
              : "Official embed unavailable"}
          </p>
          <p className="max-w-prose text-xs text-muted-foreground">
            {appliedSeek != null
              ? `Seek request applied at ${formatDuration(appliedSeek)} (verified timing only).`
              : "Citation seeks appear here when timing is verified. No fabricated YouTube media."}
          </p>
          {youtubeVideoId ? (
            <p className="font-mono text-[11px] text-muted-foreground">id: {youtubeVideoId}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}
