/** Title search stays on the videos list. It does not search transcript text. */
export function videosSearchHref(query: string): string {
  const q = query.trim();
  if (!q) return "/videos";
  return `/videos?q=${encodeURIComponent(q)}`;
}
