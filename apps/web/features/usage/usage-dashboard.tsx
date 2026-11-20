"use client";

import { useEffect, useState } from "react";

type UsagePayload = {
  period: string;
  counts: {
    jobs_used: number;
    tokens_used: number;
    requests_used: number;
    provider_runs: number;
  };
  quotas: {
    jobs_cap: number;
    tokens_cap: number;
    requests_cap: number;
    spend_cap_usd: number;
  };
  estimated_cost: {
    estimate_usd: number;
    estimate_version: string;
    is_estimate: boolean;
    disclaimer: string;
  };
};

const FIXTURE: UsagePayload = {
  period: "fixture",
  counts: {
    jobs_used: 2,
    tokens_used: 1200,
    requests_used: 8,
    provider_runs: 3,
  },
  quotas: {
    jobs_cap: 500,
    tokens_cap: 2_000_000,
    requests_cap: 10_000,
    spend_cap_usd: 25,
  },
  estimated_cost: {
    estimate_usd: 0,
    estimate_version: "v0-placeholder-not-live-rates",
    is_estimate: true,
    disclaimer:
      "Estimated cost only — not live vendor pricing. Calculation version v0-placeholder-not-live-rates. Do not use for billing or invoicing.",
  },
};

/**
 * Usage dashboard — always labels costs as estimates.
 * Fixture mode by default (no paid API); optional live GET /api/v1/usage via proxy.
 */
export function UsageDashboard() {
  const [data, setData] = useState<UsagePayload>(FIXTURE);
  const [source, setSource] = useState<"fixture" | "api">("fixture");

  useEffect(() => {
    let cancelled = false;
    const mode = process.env.NEXT_PUBLIC_LIBRARY_MODE;
    if (mode !== "api") {
      return;
    }
    void (async () => {
      try {
        const res = await fetch("/api/v1/usage", { credentials: "include" });
        if (!res.ok) return;
        const body = (await res.json()) as UsagePayload;
        if (!cancelled) {
          setData(body);
          setSource("api");
        }
      } catch {
        // Keep fixture on failure — offline-safe.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const est = data.estimated_cost;

  return (
    <div className="max-w-2xl space-y-6">
      <aside
        className="rounded-[var(--radius-panel)] border border-warning/40 bg-surface-muted px-4 py-3 text-sm text-foreground"
        role="note"
        data-testid="cost-estimate-banner"
      >
        <p className="font-medium">Costs shown are estimates</p>
        <p className="mt-1 text-muted-foreground">{est.disclaimer}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          Estimate version: <code>{est.estimate_version}</code>
          {est.is_estimate ? " · is_estimate=true" : null}
        </p>
      </aside>

      <dl className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-4">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">Period</dt>
          <dd className="mt-1 text-lg font-semibold">{data.period}</dd>
          <dd className="text-xs text-muted-foreground">Source: {source}</dd>
        </div>
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-4">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Estimated spend
          </dt>
          <dd className="mt-1 text-lg font-semibold">
            ${est.estimate_usd.toFixed(4)}{" "}
            <span className="text-sm font-normal text-muted-foreground">estimate</span>
          </dd>
          <dd className="text-xs text-muted-foreground">
            Cap ${data.quotas.spend_cap_usd.toFixed(2)}
          </dd>
        </div>
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-4">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">Jobs</dt>
          <dd className="mt-1 text-lg font-semibold">
            {data.counts.jobs_used} / {data.quotas.jobs_cap}
          </dd>
        </div>
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-4">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">Tokens</dt>
          <dd className="mt-1 text-lg font-semibold">
            {data.counts.tokens_used.toLocaleString()} /{" "}
            {data.quotas.tokens_cap.toLocaleString()}
          </dd>
        </div>
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-4">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">Requests</dt>
          <dd className="mt-1 text-lg font-semibold">
            {data.counts.requests_used} / {data.quotas.requests_cap}
          </dd>
        </div>
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-4">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Provider runs
          </dt>
          <dd className="mt-1 text-lg font-semibold">{data.counts.provider_runs}</dd>
        </div>
      </dl>
    </div>
  );
}
