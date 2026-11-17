"use client";

import { useEffect, useState } from "react";

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
          setState({ kind: "error", message: "Could not reach local health proxy" });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return <p className="muted">Checking API connectivity…</p>;
  }
  if (state.kind === "error") {
    return (
      <div className="health health-bad" role="status">
        <strong>API unreachable</strong>
        <p className="muted">{state.message}</p>
      </div>
    );
  }

  const ok = state.httpStatus === 200 && state.status === "ok";
  return (
    <div className={ok ? "health health-ok" : "health health-bad"} role="status">
      <strong>{ok ? "Backend ready" : "Backend not ready"}</strong>
      <ul>
        <li>Neon: {state.neon?.ok ? "ok" : `fail (${state.neon?.error ?? "unknown"})`}</li>
        <li>
          Qdrant Cloud:{" "}
          {state.qdrant?.ok ? "ok" : `fail (${state.qdrant?.error ?? "unknown"})`}
        </li>
      </ul>
      {state.requestId ? <p className="muted">request_id: {state.requestId}</p> : null}
    </div>
  );
}
