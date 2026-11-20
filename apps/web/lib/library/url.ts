/**
 * Client-side YouTube URL kind detection for import UX.
 * Mirrors server allowlist spirit; final validation remains on the API.
 */

export type ParsedSourceUrl =
  | {
      kind: "video";
      videoId: string;
      companionPlaylistId?: string;
      canonicalUrl: string;
    }
  | {
      kind: "playlist";
      playlistId: string;
      canonicalUrl: string;
    };

export type ParseSourceUrlError = {
  code: string;
  message: string;
};

const ALLOWED_HOSTS = new Set([
  "www.youtube.com",
  "youtube.com",
  "m.youtube.com",
  "youtu.be",
]);

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const PLAYLIST_ID_RE = /^(?:PL|UU|LL|FL|OL)[A-Za-z0-9_-]{10,64}$/;

export function parseSourceUrl(
  raw: string,
): { ok: true; value: ParsedSourceUrl } | { ok: false; error: ParseSourceUrlError } {
  const trimmed = raw.trim();
  if (!trimmed) {
    return {
      ok: false,
      error: { code: "EMPTY_URL", message: "Enter a YouTube video or playlist URL." },
    };
  }

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return {
      ok: false,
      error: { code: "INVALID_URL", message: "That does not look like a valid URL." },
    };
  }

  if (url.protocol !== "https:") {
    return {
      ok: false,
      error: { code: "INVALID_URL", message: "Only HTTPS YouTube URLs are accepted." },
    };
  }
  if (url.username || url.password) {
    return {
      ok: false,
      error: { code: "INVALID_URL", message: "URLs with embedded credentials are not allowed." },
    };
  }
  if (url.port) {
    return {
      ok: false,
      error: { code: "INVALID_URL", message: "Non-default ports are not allowed." },
    };
  }

  const host = url.hostname.replace(/\.$/, "").toLowerCase();
  if (!ALLOWED_HOSTS.has(host)) {
    return {
      ok: false,
      error: {
        code: "INVALID_HOST",
        message: "Only official YouTube hosts are allowed.",
      },
    };
  }

  const params = url.searchParams;
  const listParam = params.get("list");

  if (host === "youtu.be") {
    const id = url.pathname.replace(/^\//, "").split("/")[0] ?? "";
    if (!VIDEO_ID_RE.test(id)) {
      return {
        ok: false,
        error: { code: "INVALID_VIDEO_ID", message: "YouTube video ID is missing or invalid." },
      };
    }
    return {
      ok: true,
      value: {
        kind: "video",
        videoId: id,
        companionPlaylistId:
          listParam && PLAYLIST_ID_RE.test(listParam) ? listParam : undefined,
        canonicalUrl: `https://www.youtube.com/watch?v=${id}`,
      },
    };
  }

  const path = url.pathname;
  if (path === "/playlist" || path.startsWith("/playlist/")) {
    const playlistId = listParam ?? "";
    if (!PLAYLIST_ID_RE.test(playlistId)) {
      return {
        ok: false,
        error: {
          code: "INVALID_PLAYLIST_ID",
          message: "YouTube playlist ID is missing or invalid.",
        },
      };
    }
    return {
      ok: true,
      value: {
        kind: "playlist",
        playlistId,
        canonicalUrl: `https://www.youtube.com/playlist?list=${playlistId}`,
      },
    };
  }

  let videoId = params.get("v") ?? "";
  if (path.startsWith("/shorts/")) {
    videoId = path.split("/")[2] ?? videoId;
  } else if (path.startsWith("/embed/")) {
    videoId = path.split("/")[2] ?? videoId;
  } else if (path.startsWith("/watch")) {
    videoId = params.get("v") ?? videoId;
  }

  if (!VIDEO_ID_RE.test(videoId)) {
    return {
      ok: false,
      error: { code: "INVALID_VIDEO_ID", message: "YouTube video ID is missing or invalid." },
    };
  }

  return {
    ok: true,
    value: {
      kind: "video",
      videoId,
      companionPlaylistId:
        listParam && PLAYLIST_ID_RE.test(listParam) ? listParam : undefined,
      canonicalUrl: `https://www.youtube.com/watch?v=${videoId}`,
    },
  };
}
