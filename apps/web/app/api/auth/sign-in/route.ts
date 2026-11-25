import { NextResponse } from "next/server";

import { cookieJarFromHeader, ensureWorkspace } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const jar = cookieJarFromHeader(request.headers.get("cookie"));
  jar.delete("ll_signed_out");
  let setCookies: string[] = [];
  try {
    setCookies = await ensureWorkspace(jar);
  } catch {
    return NextResponse.json(
      { error: { code: "API_UNAVAILABLE", message: "The lesson history service is unavailable." } },
      { status: 503 },
    );
  }
  const response = NextResponse.json(
    { signed_in: jar.has("ll_access") },
    { status: jar.has("ll_access") ? 200 : 401 },
  );
  response.cookies.set("ll_signed_out", "", { path: "/", maxAge: 0 });
  for (const cookie of setCookies) {
    response.headers.append("set-cookie", cookie);
  }
  return response;
}
