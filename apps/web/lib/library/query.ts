"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { getLibraryClient } from "@/lib/library/client";
import type { TranscriptUploadInput } from "@/lib/library/types";

export const libraryKeys = {
  all: ["library"] as const,
  dashboard: () => [...libraryKeys.all, "dashboard"] as const,
  videos: (filters: { status?: string; q?: string }) =>
    [...libraryKeys.all, "videos", filters] as const,
  video: (id: string) => [...libraryKeys.all, "video", id] as const,
  playlists: (filters: { q?: string }) =>
    [...libraryKeys.all, "playlists", filters] as const,
  playlist: (id: string) => [...libraryKeys.all, "playlist", id] as const,
  playlistCourse: (id: string) => [...libraryKeys.all, "playlist-course", id] as const,
  job: (id: string) => [...libraryKeys.all, "job", id] as const,
};

export function useDashboardStats() {
  const client = getLibraryClient();
  return useQuery({
    queryKey: libraryKeys.dashboard(),
    queryFn: () => client.getDashboard(),
  });
}

export function useVideosInfinite(filters: { status?: string; q?: string }) {
  const client = getLibraryClient();
  return useInfiniteQuery({
    queryKey: libraryKeys.videos(filters),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      client.listVideos({
        cursor: pageParam,
        limit: 12,
        status: filters.status,
        q: filters.q,
      }),
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useVideo(videoId: string) {
  const client = getLibraryClient();
  return useQuery({
    queryKey: libraryKeys.video(videoId),
    queryFn: () => client.getVideo(videoId),
    enabled: Boolean(videoId),
  });
}

export function usePlaylistsInfinite(filters: { q?: string }) {
  const client = getLibraryClient();
  return useInfiniteQuery({
    queryKey: libraryKeys.playlists(filters),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      client.listPlaylists({ cursor: pageParam, limit: 12, q: filters.q }),
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function usePlaylist(playlistId: string) {
  const client = getLibraryClient();
  return useQuery({
    queryKey: libraryKeys.playlist(playlistId),
    queryFn: () => client.getPlaylist(playlistId),
    enabled: Boolean(playlistId),
  });
}

export function usePlaylistCourseSummary(playlistId: string) {
  const client = getLibraryClient();
  return useQuery({
    queryKey: libraryKeys.playlistCourse(playlistId),
    queryFn: () => client.getPlaylistCourseSummary(playlistId),
    enabled: Boolean(playlistId),
  });
}

export function useSynthesizePlaylist() {
  const client = getLibraryClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (playlistId: string) => client.synthesizePlaylist(playlistId),
    onSuccess: async (_data, playlistId) => {
      await qc.invalidateQueries({ queryKey: libraryKeys.playlistCourse(playlistId) });
      await qc.invalidateQueries({ queryKey: libraryKeys.playlist(playlistId) });
    },
  });
}

export function useJob(jobId: string | null, opts?: { enabled?: boolean }) {
  const client = getLibraryClient();
  return useQuery({
    queryKey: libraryKeys.job(jobId ?? ""),
    queryFn: () => client.getJob(jobId!),
    enabled: Boolean(jobId) && (opts?.enabled ?? true),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "succeeded" || status === "failed") return false;
      return 400;
    },
  });
}

export function useImportSource() {
  const client = getLibraryClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { youtubeUrl: string; preferPlaylist?: boolean }) =>
      client.importSource(input.youtubeUrl, { preferPlaylist: input.preferPlaylist }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: libraryKeys.all });
    },
  });
}

export function useUploadTranscript() {
  const client = getLibraryClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TranscriptUploadInput) => client.uploadTranscript(input),
    onSuccess: async (_data, vars) => {
      await qc.invalidateQueries({ queryKey: libraryKeys.video(vars.videoId) });
      await qc.invalidateQueries({ queryKey: libraryKeys.all });
    },
  });
}
