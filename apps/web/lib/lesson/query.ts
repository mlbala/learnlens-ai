"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getLessonClient } from "@/lib/lesson/client";
import type { ExplanationMode } from "@/lib/lesson/types";

export const lessonKeys = {
  all: ["lesson"] as const,
  bundle: (videoId: string) => [...lessonKeys.all, "bundle", videoId] as const,
  thread: (videoId: string) => [...lessonKeys.all, "thread", videoId] as const,
  messages: (threadId: string) => [...lessonKeys.all, "messages", threadId] as const,
};

export function useLessonBundle(videoId: string, opts?: { enabled?: boolean }) {
  const client = getLessonClient();
  return useQuery({
    queryKey: lessonKeys.bundle(videoId),
    queryFn: () => client.getLessonBundle(videoId),
    enabled: Boolean(videoId) && (opts?.enabled ?? true),
  });
}

export function useLessonThread(videoId: string, opts?: { enabled?: boolean }) {
  const client = getLessonClient();
  return useQuery({
    queryKey: lessonKeys.thread(videoId),
    queryFn: () => client.readThread(videoId),
    enabled: Boolean(videoId) && (opts?.enabled ?? true),
    staleTime: Infinity,
  });
}

export function useChatMessages(threadId: string | null | undefined) {
  const client = getLessonClient();
  return useQuery({
    queryKey: lessonKeys.messages(threadId ?? ""),
    queryFn: () => client.listMessages(threadId!),
    enabled: Boolean(threadId),
  });
}

export function usePostChatMessage(videoId: string) {
  const client = getLessonClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      threadId: string;
      question: string;
      explanationMode: ExplanationMode;
      externalSearch?: boolean;
    }) => client.postMessage({ ...input, videoId }),
    onSuccess: async (data) => {
      const threadId = data.user_message.thread_id;
      await qc.invalidateQueries({ queryKey: lessonKeys.thread(videoId) });
      await qc.invalidateQueries({ queryKey: lessonKeys.messages(threadId) });
    },
  });
}
