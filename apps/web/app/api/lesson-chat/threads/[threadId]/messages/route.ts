import { proxyLearningApi } from "@/lib/server/learning-api";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await context.params;
  return proxyLearningApi(request, `/api/v1/lesson-chat/threads/${threadId}/messages`, {
    method: "GET",
  });
}
