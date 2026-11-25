// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST as logout } from "@/app/api/auth/logout/route";
import { POST as signIn } from "@/app/api/auth/sign-in/route";
import { DELETE as removeLesson } from "@/app/api/learning-history/[videoId]/route";
import { PUT as pinLesson } from "@/app/api/learning-history/[videoId]/pin/route";

const VIDEO_ID = "11111111-1111-4111-8111-111111111111";
const SIGNED_IN = "ll_access=a; ll_refresh=r; ll_csrf=tok";

function setCookies(response: Response): string[] {
  return response.headers.getSetCookie();
}

function cookieValue(response: Response, name: string): string | undefined {
  const line = setCookies(response).find((item) => item.startsWith(`${name}=`));
  return line?.split(";")[0]?.slice(name.length + 1);
}

describe("learning-history proxy for Pin and Remove", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("passes a 204 Remove through with no body and sends CSRF", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await removeLesson(
      new Request(`http://localhost/api/learning-history/${VIDEO_ID}`, {
        method: "DELETE",
        headers: { cookie: SIGNED_IN },
      }),
      { params: Promise.resolve({ videoId: VIDEO_ID }) },
    );
    expect(response.status).toBe(204);
    expect(await response.text()).toBe("");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/api/v1/learning-history/${VIDEO_ID}$`));
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>)["x-csrf-token"]).toBe("tok");
  });

  it("forwards the Pin body and a 404 from another workspace", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json(
        { error: { code: "LESSON_NOT_IN_WORKSPACE", message: "This lesson is not in this workspace." } },
        { status: 404 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const response = await pinLesson(
      new Request(`http://localhost/api/learning-history/${VIDEO_ID}/pin`, {
        method: "PUT",
        headers: { cookie: SIGNED_IN, "content-type": "application/json" },
        body: JSON.stringify({ pinned: true }),
      }),
      { params: Promise.resolve({ videoId: VIDEO_ID }) },
    );
    expect(response.status).toBe(404);
    expect((await response.json()).error.code).toBe("LESSON_NOT_IN_WORKSPACE");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ pinned: true }));
    expect((init.headers as Record<string, string>)["x-csrf-token"]).toBe("tok");
  });
});

describe("Sign out and Sign in again", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("logs out upstream, clears session cookies, and sets ll_signed_out", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await logout(
      new Request("http://localhost/api/auth/logout", {
        method: "POST",
        headers: { cookie: SIGNED_IN },
      }),
    );
    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/auth\/logout$/);
    expect((init.headers as Record<string, string>)["x-csrf-token"]).toBe("tok");
    for (const name of ["ll_access", "ll_refresh", "ll_csrf"]) {
      expect(cookieValue(response, name)).toBe("");
    }
    expect(cookieValue(response, "ll_signed_out")).toBe("1");
  });

  it("still signs the browser out when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("down"))));
    const response = await logout(
      new Request("http://localhost/api/auth/logout", {
        method: "POST",
        headers: { cookie: SIGNED_IN },
      }),
    );
    expect(response.status).toBe(200);
    expect(cookieValue(response, "ll_signed_out")).toBe("1");
  });

  it("Sign in again clears ll_signed_out and uses the local login", async () => {
    const fetchMock = vi.fn(async () =>
      new Response("{}", {
        status: 200,
        headers: { "set-cookie": "ll_access=fresh; Path=/" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const response = await signIn(
      new Request("http://localhost/api/auth/sign-in", {
        method: "POST",
        headers: { cookie: "ll_signed_out=1" },
      }),
    );
    expect(response.status).toBe(200);
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toMatch(/\/api\/v1\/auth\/login$/);
    expect(cookieValue(response, "ll_signed_out")).toBe("");
    expect(setCookies(response).some((line) => line.startsWith("ll_access=fresh"))).toBe(true);
  });
});
