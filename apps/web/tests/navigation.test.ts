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
      "Recent Learning",
      "Settings",
    ]);
  });

  it("marks future screens as placeholders", () => {
    const placeholders = PRIMARY_NAV.filter((item) => item.placeholder);
    expect(placeholders.map((p) => p.id)).toEqual([
      "library",
      "playlists",
      "videos",
      "recent",
      "settings",
    ]);
  });
});

describe("findNavItem / breadcrumbForPath", () => {
  it("resolves home and nested paths", () => {
    expect(findNavItem("/")?.id).toBe("home");
    expect(findNavItem("/library")?.id).toBe("library");
    expect(findNavItem("/unknown")).toBeUndefined();
  });

  it("builds breadcrumbs for design-system preview", () => {
    expect(breadcrumbForPath("/design-system")).toEqual([
      { label: "Home", href: "/" },
      { label: "Design system" },
    ]);
  });

  it("falls back safely for unknown paths", () => {
    expect(breadcrumbForPath("/not-a-route")).toEqual([
      { label: "Home", href: "/" },
      { label: "Page" },
    ]);
  });
});
