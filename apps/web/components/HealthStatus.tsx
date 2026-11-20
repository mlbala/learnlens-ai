"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

type Check = { ok?: boolean; error?: string };

type HealthState =
  | { kind: "loading" }
  | {
      kind: "ready";
      status: string;
      httpStatus: number;
      neon?: Check;
      qdrant?: Check;
      requestId?: string;
    }
  | { kind: "error"; message: string };

export function HealthStatus() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/backend-health", { cache: "no-store" });
        const body = (await res.json()) as {
          status?: string;
          request_id?: string;
          checks?: { neon?: Check; qdrant?: Check };
        };
        if (cancelled) return;
        setState({
          kind: "ready",
          status: body.status ?? "unknown",
          httpStatus: res.status,
          neon: body.checks?.neon,
          qdrant: body.checks?.qdrant,
          requestId: body.request_id,
        });
      } catch {
        if (!cancelled) {
          setState({
            kind: "error",
            message: "Could not reach local health proxy",
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <div role="status" aria-label="Checking API connectivity" className="space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-36" />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <Alert variant="danger">
        <AlertTitle>API unreachable</AlertTitle>
        <AlertDescription>{state.message}</AlertDescription>
      </Alert>
    );
  }

  const ok = state.httpStatus === 200 && state.status === "ok";
  return (
    <Alert variant={ok ? "success" : "warning"} role="status">
      <AlertTitle>{ok ? "Backend ready" : "Backend not ready"}</AlertTitle>
      <AlertDescription>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-foreground">
          <li>
            Neon:{" "}
            {state.neon?.ok ? "ok" : `fail (${state.neon?.error ?? "unknown"})`}
          </li>
          <li>
            Qdrant Cloud:{" "}
            {state.qdrant?.ok
              ? "ok"
              : `fail (${state.qdrant?.error ?? "unknown"})`}
          </li>
        </ul>
        {state.requestId ? (
          <p className="mt-2 text-xs text-muted-foreground">
            request_id: {state.requestId}
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
