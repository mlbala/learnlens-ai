"use client";

import { useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LibraryApiError } from "@/lib/library/types";
import { parseSourceUrl } from "@/lib/library/url";
import { useImportSource } from "@/lib/library/query";

type ImportSourceDialogProps = {
  triggerLabel?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export function ImportSourceDialog({
  triggerLabel = "Add source",
  open: controlledOpen,
  onOpenChange,
}: ImportSourceDialogProps) {
  const router = useRouter();
  const formId = useId();
  const urlId = `${formId}-url`;
  const hintId = `${formId}-hint`;
  const errorId = `${formId}-error`;
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const open = controlledOpen ?? uncontrolledOpen;
  const setOpen = onOpenChange ?? setUncontrolledOpen;

  const [url, setUrl] = useState("");
  const [preferPlaylist, setPreferPlaylist] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const importMutation = useImportSource();

  const preview = useMemo(() => parseSourceUrl(url), [url]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!preview.ok) {
      setFormError(preview.error.message);
      return;
    }
    try {
      const result = await importMutation.mutateAsync({
        youtubeUrl: url,
        preferPlaylist:
          preferPlaylist ||
          (preview.value.kind === "video" && Boolean(preview.value.companionPlaylistId)
            ? preferPlaylist
            : preview.value.kind === "playlist"),
      });
      setOpen(false);
      setUrl("");
      setPreferPlaylist(false);
      if (result.kind === "playlist") {
        router.push(`/playlists/${result.result.playlist.id}`);
      } else {
        router.push(`/videos/${result.result.video.id}`);
      }
    } catch (err) {
      if (err instanceof LibraryApiError) {
        setFormError(err.message);
      } else {
        setFormError("Import failed. Try again.");
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {controlledOpen === undefined ? (
        <DialogTrigger asChild>
          <Button type="button">{triggerLabel}</Button>
        </DialogTrigger>
      ) : null}
      <DialogContent aria-describedby={hintId}>
        <DialogHeader>
          <DialogTitle>Add source</DialogTitle>
          <DialogDescription id={hintId}>
            Paste a YouTube video or playlist URL. Metadata import never grants transcript access
            by itself — upload a permitted transcript after import.
          </DialogDescription>
        </DialogHeader>
        <form id={formId} className="space-y-4" onSubmit={(e) => void onSubmit(e)} noValidate>
          <div className="space-y-2">
            <Label htmlFor={urlId}>YouTube URL</Label>
            <Input
              id={urlId}
              name="youtube_url"
              type="url"
              inputMode="url"
              autoComplete="off"
              placeholder="https://www.youtube.com/watch?v=vidPublic01"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              aria-invalid={formError ? true : undefined}
              aria-describedby={formError ? errorId : hintId}
            />
            {preview.ok ? (
              <p className="text-xs text-muted-foreground">
                Detected: {preview.value.kind}
                {preview.value.kind === "video" && preview.value.companionPlaylistId
                  ? " (companion playlist available)"
                  : ""}
              </p>
            ) : url.trim() ? (
              <p className="text-xs text-danger">{preview.error.message}</p>
            ) : null}
          </div>

          {preview.ok &&
          preview.value.kind === "video" &&
          preview.value.companionPlaylistId ? (
            <label className="flex min-h-11 items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={preferPlaylist}
                onChange={(e) => setPreferPlaylist(e.target.checked)}
              />
              <span>
                Import the companion playlist instead of this single video
                <span className="block text-xs text-muted-foreground">
                  {preview.value.companionPlaylistId}
                </span>
              </span>
            </label>
          ) : null}

          {formError ? (
            <p id={errorId} role="alert" className="text-sm text-danger">
              {formError}
            </p>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={importMutation.isPending || !url.trim()}>
              {importMutation.isPending ? "Importing…" : "Import metadata"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
