// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { cookieJarFromHeader, ensureWorkspace, proxyLearningApi } from "@/lib/server/learning-api";

describe("ll_signed_out", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stops ensureWorkspace from logging the local user back in", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const jar = cookieJarFromHeader("ll_signed_out=1");
    const cookies = await ensureWorkspace(jar);
    expect(cookies).toEqual([]);
    expect(jar.has("ll_access")).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps a learning-history call signed out until Sign in again", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://localhost/api/learning-history", {
      headers: { cookie: "ll_signed_out=1; ll_access=stale; ll_csrf=stale" },
    });
    const response = await proxyLearningApi(request, "/api/v1/learning-history", {
      method: "GET",
    });
    expect(response.status).toBe(401);
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logs in when the signed-out cookie is absent", async () => {
    const fetchMock = vi.fn(async () =>
      new Response("{}", {
        status: 200,
        headers: { "set-cookie": "ll_access=a; Path=/" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const jar = cookieJarFromHeader(null);
    await ensureWorkspace(jar);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(jar.get("ll_access")).toBe("a");
  });
});
