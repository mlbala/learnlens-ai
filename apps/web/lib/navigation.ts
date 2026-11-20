/**
 * Primary IA from docs/07_UI_UX_DESIGN_SYSTEM.md §3.
 * Phase 09: shell destinations only — functional pages arrive in later phases.
 */

export type NavItem = {
  id: string;
  label: string;
  href: string;
  /** When true, destination is a shell placeholder (phase 10+). */
  placeholder?: boolean;
};

export const PRIMARY_NAV: readonly NavItem[] = [
  { id: "home", label: "Home", href: "/" },
  { id: "library", label: "My Library", href: "/library", placeholder: true },
  { id: "playlists", label: "Playlists", href: "/playlists", placeholder: true },
  { id: "videos", label: "Videos", href: "/videos", placeholder: true },
  { id: "recent", label: "Recent Learning", href: "/recent", placeholder: true },
  { id: "settings", label: "Settings", href: "/settings", placeholder: true },
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
  const item = findNavItem(pathname);
  if (item) {
    return [{ label: "Home", href: "/" }, { label: item.label }];
  }
  return [{ label: "Home", href: "/" }, { label: "Page" }];
}
