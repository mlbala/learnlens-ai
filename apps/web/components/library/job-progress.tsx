"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useJob } from "@/lib/library/query";

type JobProgressProps = {
  jobId: string | null;
  onRetry?: () => void;
};

export function JobProgress({ jobId, onRetry }: JobProgressProps) {
  const query = useJob(jobId);

  if (!jobId) return null;

  if (query.isLoading) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        Checking job status…
      </p>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="danger">
        <AlertTitle>Could not load job status</AlertTitle>
        <AlertDescription>
          <p>{query.error instanceof Error ? query.error.message : "Unknown error"}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => void query.refetch()}
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const job = query.data;
  if (!job) return null;

  const failed = job.status === "failed";
  const done = job.status === "succeeded";

  return (
    <div className="space-y-2 rounded-[var(--radius-card)] border border-border bg-surface p-4" role="status">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-foreground">
          {done ? "Transcript processed" : failed ? "Processing interrupted" : "Processing transcript"}
        </p>
        <span className="text-xs tabular-nums text-muted-foreground">{job.percent}%</span>
      </div>
      <Progress value={job.percent} label={`Job ${job.stage} ${job.percent} percent`} />
      <p className="text-xs text-muted-foreground">
        Stage: {job.stage}
        {job.last_error_code ? ` · ${job.last_error_code}` : null}
      </p>
      {failed && onRetry ? (
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          Retry upload
        </Button>
      ) : null}
    </div>
  );
}
