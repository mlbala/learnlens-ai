"use client";

import { useId, useState } from "react";

import { JobProgress } from "@/components/library/job-progress";
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
import { useUploadTranscript } from "@/lib/library/query";

type TranscriptImportDialogProps = {
  videoId: string;
  videoTitle: string;
  disabled?: boolean;
  disabledReason?: string;
};

type Method = "upload" | "paste";

export function TranscriptImportDialog({
  videoId,
  videoTitle,
  disabled,
  disabledReason,
}: TranscriptImportDialogProps) {
  const formId = useId();
  const [open, setOpen] = useState(false);
  const [method, setMethod] = useState<Method>("upload");
  const [attested, setAttested] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const upload = useUploadTranscript();

  const attestId = `${formId}-attest`;
  const errorId = `${formId}-error`;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!attested) {
      setError("Attestation is required before upload.");
      return;
    }
    try {
      const sourceKind =
        method === "paste"
          ? "paste"
          : file?.name.toLowerCase().endsWith(".vtt")
            ? "vtt"
            : file?.name.toLowerCase().endsWith(".srt")
              ? "srt"
              : "txt";
      const result = await upload.mutateAsync({
        videoId,
        rightsAttested: true,
        sourceKind,
        pasteText: method === "paste" ? pasteText : undefined,
        file: method === "upload" ? file ?? undefined : undefined,
      });
      setJobId(result.job_id);
    } catch (err) {
      if (err instanceof LibraryApiError) setError(err.message);
      else setError("Upload failed. Try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setError(null);
          setJobId(null);
          setAttested(false);
          setPasteText("");
          setFile(null);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          type="button"
          disabled={disabled}
          aria-describedby={disabled && disabledReason ? `${formId}-disabled` : undefined}
        >
          Add transcript
        </Button>
      </DialogTrigger>
      {disabled && disabledReason ? (
        <p id={`${formId}-disabled`} className="sr-only">
          {disabledReason}
        </p>
      ) : null}
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Upload permitted transcript</DialogTitle>
          <DialogDescription>
            Attach a rights-attested SRT, VTT, TXT, or pasted transcript for “{videoTitle}”.
            This does not download YouTube media or captions.
          </DialogDescription>
        </DialogHeader>

        {jobId ? (
          <div className="space-y-4">
            <JobProgress jobId={jobId} onRetry={() => setJobId(null)} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Close
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={(e) => void onSubmit(e)} noValidate>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Source method</legend>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={method === "upload" ? "default" : "outline"}
                  onClick={() => setMethod("upload")}
                  aria-pressed={method === "upload"}
                >
                  Upload permitted subtitles
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={method === "paste" ? "default" : "outline"}
                  onClick={() => setMethod("paste")}
                  aria-pressed={method === "paste"}
                >
                  Paste permitted transcript
                </Button>
                <Button type="button" size="sm" variant="outline" disabled aria-disabled>
                  Owner-authorized captions (not configured)
                </Button>
              </div>
            </fieldset>

            {method === "upload" ? (
              <div className="space-y-2">
                <Label htmlFor={`${formId}-file`}>Subtitle file (.srt, .vtt, .txt)</Label>
                <Input
                  id={`${formId}-file`}
                  type="file"
                  accept=".srt,.vtt,.txt,text/plain,text/vtt"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor={`${formId}-paste`}>Transcript text</Label>
                <textarea
                  id={`${formId}-paste`}
                  className="min-h-32 w-full rounded-[var(--radius-control)] border border-border bg-surface px-3 py-2 text-sm"
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder="Paste permitted transcript text (fixture data only in demo mode)"
                />
              </div>
            )}

            <label className="flex min-h-11 items-start gap-2 text-sm" htmlFor={attestId}>
              <input
                id={attestId}
                type="checkbox"
                className="mt-1"
                checked={attested}
                onChange={(e) => setAttested(e.target.checked)}
                required
              />
              <span>
                I own this transcript or have the necessary permission to process it.
              </span>
            </label>

            {error ? (
              <p id={errorId} role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={upload.isPending || !attested}>
                {upload.isPending ? "Uploading…" : "Start processing"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
