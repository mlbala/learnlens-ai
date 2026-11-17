/** Server-side FastAPI base URL (never put secrets in NEXT_PUBLIC_*). */

export function getApiBaseUrl(): string {
  return (
    process.env.API_INTERNAL_URL?.trim() ||
    process.env.API_URL?.trim() ||
    "http://127.0.0.1:8000"
  );
}

export type ReadyPayload = {
  status: string;
  request_id?: string;
  checks?: {
    neon?: { ok?: boolean; error?: string };
    qdrant?: { ok?: boolean; error?: string };
  };
};
