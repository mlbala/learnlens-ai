import { proxyLearningApi } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ videoId: string }> }) {
  const { videoId } = await context.params;
  return proxyLearningApi(request, `/api/v1/lesson-chat/videos/${videoId}`, { method: "GET" });
}
