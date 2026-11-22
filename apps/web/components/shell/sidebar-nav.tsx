"use client";

import {
  BookOpen,
  Clock3,
  Film,
  Home,
  Library,
  ListVideo,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";

import { PRIMARY_NAV, type NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  home: Home,
  library: Library,
  playlists: ListVideo,
  videos: Film,
  recent: Clock3,
  settings: Settings,
};

type SidebarNavProps = {
  onNavigate?: () => void;
  className?: string;
};

function isActive(pathname: string, item: NavItem): boolean {
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export function SidebarNav({ onNavigate, className }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className={cn("flex flex-col gap-1", className)}>
      {PRIMARY_NAV.map((item) => {
        const Icon = ICONS[item.id] ?? BookOpen;
        const active = isActive(pathname, item);
        return (
          <Link
            key={item.id}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex min-h-10 items-center gap-3 rounded-[var(--radius-control)] px-3 text-sm font-medium transition-colors duration-150",
              active
                ? "bg-primary/10 text-primary before:absolute before:inset-y-2 before:-left-3 before:w-1 before:rounded-r-full before:bg-primary"
                : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            <span className="truncate">{item.label}</span>
            {item.placeholder ? (
              <span className="ml-auto text-[10px] font-normal uppercase tracking-wide text-muted-foreground">
                soon
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
