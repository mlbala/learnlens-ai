/**
 * Same-origin proxy from the web app to FastAPI lesson history.
 * The browser never receives provider keys. A local development workspace
 * is created on first use so a refresh can read Neon without a separate login screen.
 */

import { NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

const DEV_EMAIL = process.env.WEB_WORKSPACE_EMAIL?.trim() || "learner@example.com";
const DEV_PASSWORD = process.env.WEB_WORKSPACE_PASSWORD?.trim() || "learnlens-local-1";

type CookieJar = Map<string, string>;

function parseCookieHeader(header: string | null): CookieJar {
  const jar: CookieJar = new Map();
  if (!header) return jar;
  for (const part of header.split(";")) {
    const trimmed = part.trim();
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    jar.set(trimmed.slice(0, eq), trimmed.slice(eq + 1));
  }
  return jar;
}

export function cookieJarFromHeader(header: string | null): CookieJar {
  return parseCookieHeader(header);
}

function serializeJar(jar: CookieJar): string {
  return [...jar.entries()].map(([name, value]) => `${name}=${value}`).join("; ");
}

function absorbSetCookies(jar: CookieJar, response: Response): string[] {
  const lines =
    typeof response.headers.getSetCookie === "function" ? response.headers.getSetCookie() : [];
  for (const line of lines) {
    const pair = line.split(";")[0] ?? "";
    const eq = pair.indexOf("=");
    if (eq <= 0) continue;
    jar.set(pair.slice(0, eq).trim(), pair.slice(eq + 1).trim());
  }
  return lines;
}

function csrfToken(jar: CookieJar): string | undefined {
  const token = jar.get("ll_csrf");
  return token || undefined;
}

async function authCall(
  path: string,
  body: Record<string, string>,
): Promise<{ ok: boolean; jar: CookieJar; setCookies: string[] }> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const jar: CookieJar = new Map();
  const setCookies = absorbSetCookies(jar, response);
  return { ok: response.ok, jar, setCookies };
}

export async function ensureWorkspace(jar: CookieJar): Promise<string[]> {
  if (jar.get("ll_signed_out") === "1") {
    jar.delete("ll_access");
    jar.delete("ll_refresh");
    jar.delete("ll_csrf");
    return [];
  }
  if (jar.has("ll_access") && jar.has("ll_csrf")) return [];
  if (process.env.NODE_ENV === "production" && !process.env.WEB_WORKSPACE_PASSWORD) return [];

  let attempt = await authCall("/api/v1/auth/login", {
    email: DEV_EMAIL,
    password: DEV_PASSWORD,
  });
  if (!attempt.ok) {
    attempt = await authCall("/api/v1/auth/register", {
      email: DEV_EMAIL,
      password: DEV_PASSWORD,
      name: "Learner",
    });
    if (!attempt.ok) {
      attempt = await authCall("/api/v1/auth/login", {
        email: DEV_EMAIL,
        password: DEV_PASSWORD,
      });
    }
  }
  if (!attempt.ok || !attempt.jar.has("ll_access")) return [];
  for (const [name, value] of attempt.jar) jar.set(name, value);
  return attempt.setCookies;
}

async function refreshSession(jar: CookieJar): Promise<string[]> {
  const token = csrfToken(jar);
  if (!jar.has("ll_refresh") || !token) return [];
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
    method: "POST",
    headers: {
      accept: "application/json",
      cookie: serializeJar(jar),
      "x-csrf-token": token,
    },
    cache: "no-store",
  });
  const lines = absorbSetCookies(jar, response);
  return response.ok ? lines : [];
}

export async function proxyLearningApi(
  request: Request,
  path: string,
  init: { method: string; body?: string },
): Promise<NextResponse> {
  const jar = parseCookieHeader(request.headers.get("cookie"));
  let setCookies: string[] = [];
  try {
    setCookies = await ensureWorkspace(jar);
  } catch {
    return NextResponse.json(
      { error: { code: "API_UNAVAILABLE", message: "The lesson history service is unavailable." } },
      { status: 503 },
    );
  }
  if (!jar.has("ll_access")) {
    return NextResponse.json(
      { error: { code: "AUTH_REQUIRED", message: "Sign in is required to save lessons." } },
      { status: 401 },
    );
  }

  const send = async () => {
    const headers: Record<string, string> = {
      accept: "application/json",
      cookie: serializeJar(jar),
    };
    if (init.body) headers["content-type"] = "application/json";
    const token = csrfToken(jar);
    if (token && init.method !== "GET" && init.method !== "HEAD") {
      headers["x-csrf-token"] = token;
    }
    return fetch(`${getApiBaseUrl()}${path}`, {
      method: init.method,
      headers,
      body: init.body,
      cache: "no-store",
    });
  };

  let upstream: Response;
  try {
    upstream = await send();
    if (upstream.status === 401) {
      const refreshed = await refreshSession(jar);
      setCookies = [...setCookies, ...refreshed];
      if (refreshed.length === 0) {
        setCookies = [...setCookies, ...(await ensureWorkspace(jar))];
      }
      if (jar.has("ll_access")) upstream = await send();
    }
  } catch {
    return NextResponse.json(
      { error: { code: "API_UNAVAILABLE", message: "The lesson history service is unavailable." } },
      { status: 503 },
    );
  }

  let response: NextResponse;
  if (upstream.status === 204) {
    // A null-body status cannot carry JSON. Remove returns 204.
    response = new NextResponse(null, { status: 204 });
  } else {
    const payload = await upstream.json().catch(() => null);
    response = NextResponse.json(
      payload ?? { error: { code: "UPSTREAM", message: "Lesson history is unavailable." } },
      { status: upstream.status },
    );
  }
  const upstreamCookies =
    typeof upstream.headers.getSetCookie === "function" ? upstream.headers.getSetCookie() : [];
  for (const cookie of [...setCookies, ...upstreamCookies]) {
    response.headers.append("set-cookie", cookie);
  }
  return response;
}
