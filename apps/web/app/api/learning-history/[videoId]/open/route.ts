import { proxyLearningApi } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ videoId: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { videoId } = await context.params;
  return proxyLearningApi(request, `/api/v1/learning-history/${videoId}/open`, {
    method: "POST",
  });
}
