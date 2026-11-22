/**
 * Primary IA from docs/07_UI_UX_DESIGN_SYSTEM.md §3.
 * Phase 10: library / playlist / video screens are live; later phases remain placeholders.
 */

export type NavItem = {
  id: string;
  label: string;
  href: string;
  /** When true, destination is a shell placeholder (later phases). */
  placeholder?: boolean;
};

export const PRIMARY_NAV: readonly NavItem[] = [
  { id: "home", label: "Home", href: "/" },
  { id: "library", label: "My Library", href: "/library" },
  { id: "playlists", label: "Playlists", href: "/playlists" },
  { id: "videos", label: "Videos", href: "/videos" },
  { id: "practice", label: "Practice", href: "/practice" },
  { id: "recent", label: "Recent Learning", href: "/recent" },
  { id: "settings", label: "Settings", href: "/settings" },
] as const;

export const CONTENT_TABS = [
  "Overview",
  "Chapters",
  "Summary",
  "Ask AI",
  "Transcript",
  "Study Notes",
] as const;

export type ContentTab = (typeof CONTENT_TABS)[number];

export function findNavItem(pathname: string): NavItem | undefined {
  const exact = PRIMARY_NAV.find((item) => item.href === pathname);
  if (exact) return exact;
  return PRIMARY_NAV.find(
    (item) => item.href !== "/" && pathname.startsWith(`${item.href}/`),
  );
}

export function breadcrumbForPath(pathname: string): { label: string; href?: string }[] {
  if (pathname === "/" || pathname === "") {
    return [{ label: "Home" }];
  }
  if (pathname === "/design-system") {
    return [{ label: "Home", href: "/" }, { label: "Design system" }];
  }
  if (pathname === "/import") {
    return [{ label: "Home", href: "/" }, { label: "Import source" }];
  }
  if (pathname === "/practice") {
    return [{ label: "Home", href: "/" }, { label: "Practice" }];
  }
  const videoMatch = pathname.match(/^\/videos\/([^/]+)$/);
  if (videoMatch) {
    return [
      { label: "Home", href: "/" },
      { label: "Videos", href: "/videos" },
      { label: "Overview" },
    ];
  }
  const playlistMatch = pathname.match(/^\/playlists\/([^/]+)$/);
  if (playlistMatch) {
    return [
      { label: "Home", href: "/" },
      { label: "Playlists", href: "/playlists" },
      { label: "Overview" },
    ];
  }
  const item = findNavItem(pathname);
  if (item) {
    return [{ label: "Home", href: "/" }, { label: item.label }];
  }
  return [{ label: "Home", href: "/" }, { label: "Page" }];
}
