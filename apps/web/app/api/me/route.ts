import { proxyLearningApi } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyLearningApi(request, "/api/v1/me", { method: "GET" });
}
