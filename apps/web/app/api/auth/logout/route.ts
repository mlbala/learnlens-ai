import { NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";

function csrfFromCookie(header: string): string | undefined {
  const match = header.match(/(?:^|;\s*)ll_csrf=([^;]+)/);
  return match?.[1] || undefined;
}

export async function POST(request: Request) {
  const cookie = request.headers.get("cookie") ?? "";
  const csrf = csrfFromCookie(cookie);
  if (csrf) {
    await fetch(`${getApiBaseUrl()}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        accept: "application/json",
        cookie,
        "x-csrf-token": decodeURIComponent(csrf),
      },
      cache: "no-store",
    }).catch(() => undefined);
  }
  const response = NextResponse.json({ signed_out: true });
  for (const name of ["ll_access", "ll_refresh", "ll_csrf"]) {
    response.cookies.set(name, "", { path: "/", maxAge: 0 });
  }
  response.cookies.set("ll_signed_out", "1", {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
  });
  return response;
}
