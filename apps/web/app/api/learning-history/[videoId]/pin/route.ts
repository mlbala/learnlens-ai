import { proxyLearningApi } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ videoId: string }> };

export async function PUT(request: Request, context: RouteContext) {
  const { videoId } = await context.params;
  const body = await request.text();
  return proxyLearningApi(request, `/api/v1/learning-history/${videoId}/pin`, {
    method: "PUT",
    body,
  });
}
