import { proxyLearningApi } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyLearningApi(request, "/api/v1/learning-history", { method: "GET" });
}

export async function POST(request: Request) {
  const body = await request.text();
  return proxyLearningApi(request, "/api/v1/learning-history", { method: "POST", body });
}
