import { describe, expect, it } from "vitest";

import {
  breadcrumbForPath,
  findNavItem,
  PRIMARY_NAV,
} from "@/lib/navigation";

describe("PRIMARY_NAV", () => {
  it("includes required IA destinations", () => {
    const labels = PRIMARY_NAV.map((item) => item.label);
    expect(labels).toEqual([
      "Home",
      "My Library",
      "Playlists",
      "Videos",
      "Practice",
      "Recent Learning",
      "Settings",
    ]);
  });

  it("marks only later-phase screens as placeholders", () => {
    const placeholders = PRIMARY_NAV.filter((item) => item.placeholder);
    expect(placeholders.map((p) => p.id)).toEqual([]);
  });
});

describe("findNavItem / breadcrumbForPath", () => {
  it("resolves home and nested paths", () => {
    expect(findNavItem("/")?.id).toBe("home");
    expect(findNavItem("/library")?.id).toBe("library");
    expect(findNavItem("/unknown")).toBeUndefined();
  });

  it("builds breadcrumbs for design-system and detail routes", () => {
    expect(breadcrumbForPath("/design-system")).toEqual([
      { label: "Home", href: "/" },
      { label: "Design system" },
    ]);
    expect(breadcrumbForPath("/videos/abc")).toEqual([
      { label: "Home", href: "/" },
      { label: "Videos", href: "/videos" },
      { label: "Overview" },
    ]);
    expect(breadcrumbForPath("/playlists/xyz")).toEqual([
      { label: "Home", href: "/" },
      { label: "Playlists", href: "/playlists" },
      { label: "Overview" },
    ]);
  });

  it("falls back safely for unknown paths", () => {
    expect(breadcrumbForPath("/not-a-route")).toEqual([
      { label: "Home", href: "/" },
      { label: "Page" },
    ]);
  });
});
