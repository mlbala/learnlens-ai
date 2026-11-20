import Link from "next/link";

import { SidebarNav } from "@/components/shell/sidebar-nav";
import { Separator } from "@/components/ui/separator";

export function AppSidebar() {
  return (
    <aside
      className="hidden w-[var(--sidebar-width)] shrink-0 border-r border-border bg-surface lg:flex lg:flex-col"
      aria-label="Application sidebar"
    >
      <div className="flex h-14 items-center px-5">
        <Link
          href="/"
          className="text-base font-semibold tracking-tight text-foreground"
        >
          LearnLens <span className="text-primary">AI</span>
        </Link>
      </div>
      <Separator />
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav />
      </div>
      <div className="space-y-2 border-t border-border px-4 py-3">
        <p className="text-xs text-muted-foreground">
          Turn supported transcripts into lessons and cited answers.
        </p>
        <Link
          href="/design-system"
          className="block text-xs font-medium text-primary hover:text-primary-hover"
        >
          Design system
        </Link>
      </div>
    </aside>
  );
}
