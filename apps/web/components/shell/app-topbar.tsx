"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { ProviderBadge } from "@/components/patterns/provider-badge";
import { AccountStatus } from "@/components/shell/account-status";
import { BrandMark } from "@/components/shell/brand-mark";
import { MobileNav } from "@/components/shell/mobile-nav";
import { usePageTitleValue } from "@/components/shell/page-title";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { videosSearchHref } from "@/lib/library/search-href";
import { breadcrumbForPath } from "@/lib/navigation";

type AppTopbarProps = {
  providerLabel?: string;
  providerConfigured?: boolean;
};

export function AppTopbar({
  providerLabel = "fake",
  providerConfigured = true,
}: AppTopbarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [search, setSearch] = useState("");
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
          <form
            role="search"
            className="relative hidden w-56 lg:block xl:w-72"
            onSubmit={(event) => {
              event.preventDefault();
              // Saved lesson titles only. Transcript text, chat, and outside snippets are not searched.
              router.push(videosSearchHref(search));
            }}
          >
            <Label htmlFor="app-search" className="sr-only">
              Search lesson titles
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
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              autoComplete="off"
            />
          </form>
          <ProviderBadge
            providerLabel={providerLabel}
            configured={providerConfigured}
            className="hidden shrink-0 sm:inline-flex"
          />
          <ThemeToggle />
          <AccountStatus />
        </div>
      </div>
    </header>
  );
}
