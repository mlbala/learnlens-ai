"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { usePathname } from "next/navigation";

import { ProviderBadge } from "@/components/patterns/provider-badge";
import { MobileNav } from "@/components/shell/mobile-nav";
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
  const crumbs = breadcrumbForPath(pathname);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <MobileNav />

        <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1 text-sm md:flex">
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

        <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-2 sm:max-w-md lg:max-w-sm">
          <div className="relative hidden w-full sm:block">
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
              className="pl-9"
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
            className="hidden max-w-[9rem] truncate rounded-[var(--radius-control)] border border-border px-2 py-1.5 text-xs text-muted-foreground md:block"
            title={workspaceLabel}
          >
            {workspaceLabel}
          </div>
        </div>
      </div>
    </header>
  );
}
