"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { VideoRecord } from "@/lib/library/types";

export const REMOVE_CONFIRM =
  "Remove this lesson? This deletes the lesson, its notes, and its Ask AI thread.";

type LessonLike = Pick<VideoRecord, "transcript_access" | "fixture_data" | "metadata_json">;

/**
 * A saved Gemini lesson: transcript access, not fixture data, and Gemini lesson metadata.
 * A video with a permitted transcript upload also has transcript access but is not a lesson,
 * and the learning-history API answers 404 for it, so it gets no Pin or Remove.
 */
export function isGeminiLesson(video: LessonLike) {
  const meta = video.metadata_json;
  const lesson = meta && typeof meta === "object" ? meta.gemini_lesson : null;
  const hasLesson = Boolean(lesson && typeof lesson === "object");
  return Boolean(video.transcript_access) && !video.fixture_data && hasLesson;
}

type LessonControlsProps = {
  videoId: string;
  title?: string;
  pinned?: boolean;
  /** Refresh lists after a pin change or a removal. */
  onChanged?: () => void;
  /** The server accepted a new pin state. */
  onPinnedChange?: (pinned: boolean) => void;
  /** Called once the lesson no longer exists in this workspace. */
  afterRemove?: () => void;
};

export function LessonControls({
  videoId,
  title,
  pinned = false,
  onChanged,
  onPinnedChange,
  afterRemove,
}: LessonControlsProps) {
  const [busy, setBusy] = useState(false);
  const [keptPinned, setKeptPinned] = useState(pinned);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setKeptPinned(pinned);
  }, [pinned]);

  async function onRemove() {
    if (!window.confirm(REMOVE_CONFIRM)) return;
    setBusy(true);
    setError(null);
    const res = await fetch(`/api/learning-history/${videoId}`, {
      method: "DELETE",
      credentials: "include",
    }).catch(() => null);
    setBusy(false);
    // 404 means it is already gone from this workspace; treat as removed.
    if (!res || (!res.ok && res.status !== 404)) {
      setError("Could not remove this lesson.");
      return;
    }
    onChanged?.();
    afterRemove?.();
  }

  async function onPin() {
    const next = !keptPinned;
    setBusy(true);
    setError(null);
    const res = await fetch(`/api/learning-history/${videoId}/pin`, {
      method: "PUT",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ pinned: next }),
    }).catch(() => null);
    setBusy(false);
    if (res?.status === 404) {
      // Do not navigate away as if removed; say so and let the list refresh.
      setError("This lesson is no longer in this workspace.");
      onChanged?.();
      return;
    }
    if (!res?.ok) {
      setError(next ? "Could not pin this lesson." : "Could not unpin this lesson.");
      return;
    }
    setKeptPinned(next);
    onPinnedChange?.(next);
    onChanged?.();
  }

  const label = title ? ` ${title}` : "";

  return (
    <div className="flex shrink-0 flex-wrap items-center gap-1">
      {keptPinned ? (
        <span className="px-1 text-xs font-medium text-primary">Pinned</span>
      ) : null}
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy}
        aria-pressed={keptPinned}
        aria-label={`${keptPinned ? "Unpin" : "Pin"}${label}`}
        onClick={() => void onPin()}
      >
        {keptPinned ? "Unpin" : "Pin"}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy}
        aria-label={`Remove${label}`}
        onClick={() => void onRemove()}
      >
        Remove
      </Button>
      {error ? (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      ) : null}
    </div>
  );
}
