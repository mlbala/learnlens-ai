import Link from "next/link";

import { BrandMark } from "@/components/shell/brand-mark";
import { SidebarNav } from "@/components/shell/sidebar-nav";
import { Separator } from "@/components/ui/separator";

export function AppSidebar() {
  return (
    <aside
      className="sticky top-0 hidden h-screen w-[var(--sidebar-width)] shrink-0 border-r border-border bg-surface lg:flex lg:flex-col"
      aria-label="Application sidebar"
    >
      <div className="flex h-14 items-center px-4">
        <Link href="/" className="flex items-center gap-2.5">
          <BrandMark />
          <span className="text-base font-semibold tracking-tight text-foreground">
            LearnLens <span className="text-primary">AI</span>
          </span>
        </Link>
      </div>
      <Separator />
      <div className="scroll-quiet flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav />
      </div>
      <div className="p-3">
        <div className="rounded-[var(--radius-card)] border border-border bg-surface-muted/70 px-3 py-3">
          <p className="text-xs font-medium text-foreground">Learn from any video</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Paste a YouTube link. Gemini builds the lesson from the public video.
          </p>
        </div>
      </div>
    </aside>
  );
}
