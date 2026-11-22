"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { usePathname } from "next/navigation";

import { ProviderBadge } from "@/components/patterns/provider-badge";
import { BrandMark } from "@/components/shell/brand-mark";
import { MobileNav } from "@/components/shell/mobile-nav";
import { usePageTitleValue } from "@/components/shell/page-title";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { breadcrumbForPath } from "@/lib/navigation";

type AppTopbarProps = {
  /** Fixture display name — not a live auth session claim. */
  workspaceLabel?: string;
  providerLabel?: string;
  providerConfigured?: boolean;
};

export function AppTopbar({
  workspaceLabel = "Personal workspace",
  providerLabel = "fake",
  providerConfigured = true,
}: AppTopbarProps) {
  const pathname = usePathname();
  const pageTitle = usePageTitleValue();
  const crumbs = breadcrumbForPath(pathname).map((crumb, index, all) => {
    const isLast = index === all.length - 1;
    if (!isLast || !pageTitle || !pathname.startsWith("/videos/")) return crumb;
    return { ...crumb, label: pageTitle };
  });

  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-surface/80 backdrop-blur-md supports-[backdrop-filter]:bg-surface/70">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <MobileNav />
        <Link href="/" className="flex shrink-0 items-center gap-2 lg:hidden" aria-label="LearnLens AI home">
          <BrandMark className="h-6 w-6" />
        </Link>

        <nav aria-label="Breadcrumb" className="hidden min-w-0 flex-1 items-center gap-1 text-sm md:flex">
          <ol className="flex min-w-0 items-center gap-1">
            {crumbs.map((crumb, index) => {
              const isLast = index === crumbs.length - 1;
              return (
                <li key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                  {index > 0 ? (
                    <span className="text-muted-foreground" aria-hidden>
                      /
                    </span>
                  ) : null}
                  {crumb.href && !isLast ? (
                    <Link
                      href={crumb.href}
                      className="truncate text-muted-foreground hover:text-foreground"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span
                      className="truncate font-medium text-foreground"
                      aria-current={isLast ? "page" : undefined}
                    >
                      {crumb.label}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <div className="relative hidden w-56 lg:block xl:w-72">
            <Label htmlFor="app-search" className="sr-only">
              Search library titles
            </Label>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="app-search"
              type="search"
              placeholder="Search titles…"
              className="h-9 pl-9"
              disabled
              aria-describedby="app-search-hint"
            />
            <p id="app-search-hint" className="sr-only">
              Search connects in a later phase. Control is disabled for now.
            </p>
          </div>
          <ProviderBadge
            providerLabel={providerLabel}
            configured={providerConfigured}
            className="hidden shrink-0 sm:inline-flex"
          />
          <ThemeToggle />
          <div
            className="hidden h-9 max-w-[9rem] items-center truncate rounded-[var(--radius-control)] border border-border px-2 text-xs leading-9 text-muted-foreground xl:flex"
            title={workspaceLabel}
          >
            {workspaceLabel}
          </div>
        </div>
      </div>
    </header>
  );
}
