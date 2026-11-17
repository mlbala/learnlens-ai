import { NextResponse } from "next/server";

import { getApiBaseUrl, type ReadyPayload } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Same-origin proxy to FastAPI /health/ready (no secrets exposed to the browser). */
export async function GET(): Promise<NextResponse> {
  const base = getApiBaseUrl();
  try {
    const upstream = await fetch(`${base}/health/ready`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const body = (await upstream.json()) as ReadyPayload;
    return NextResponse.json(body, { status: upstream.status });
  } catch (error) {
    const message = error instanceof Error ? error.name : "FetchError";
    return NextResponse.json(
      {
        status: "unreachable",
        checks: {
          neon: { ok: false, error: message },
          qdrant: { ok: false, error: message },
        },
      },
      { status: 503 },
    );
  }
}
