import { NextResponse } from "next/server";

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

/** Public oEmbed title lookup. No YouTube Data API key and no caption download. */
export async function GET(request: Request) {
  const videoId = new URL(request.url).searchParams.get("videoId") ?? "";
  if (!VIDEO_ID_RE.test(videoId) || videoId.startsWith("vid")) {
    return NextResponse.json({ error: "invalid_video_id" }, { status: 400 });
  }

  const watch = `https://www.youtube.com/watch?v=${videoId}`;
  const endpoint = `https://www.youtube.com/oembed?url=${encodeURIComponent(watch)}&format=json`;
  try {
    const res = await fetch(endpoint, { next: { revalidate: 3600 } });
    if (!res.ok) {
      return NextResponse.json({ error: "oembed_unavailable" }, { status: 404 });
    }
    const body = (await res.json()) as { title?: string; author_name?: string };
    return NextResponse.json({
      videoId,
      title: typeof body.title === "string" ? body.title : "",
      author_name: typeof body.author_name === "string" ? body.author_name : "",
    });
  } catch {
    return NextResponse.json({ error: "oembed_unavailable" }, { status: 502 });
  }
}
