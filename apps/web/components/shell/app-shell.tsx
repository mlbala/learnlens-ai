import type { ReactNode } from "react";

import { AppSidebar } from "@/components/shell/app-sidebar";
import { AppTopbar } from "@/components/shell/app-topbar";
import { PageTitleProvider } from "@/components/shell/page-title";

type AppShellProps = {
  children: ReactNode;
};

function runtimeEnv(name: string): string {
  return (process.env[name] ?? "").trim();
}

/** Authenticated application chrome — desktop sidebar + topbar + mobile nav. */
export function AppShell({ children }: AppShellProps) {
  const provider = runtimeEnv("AI_CHAT_PROVIDER") || "gemini";
  const configured = provider === "gemini" ? Boolean(runtimeEnv("GEMINI_API_KEY")) : true;
  return (
    <PageTitleProvider>
      <div className="flex min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-[var(--radius-control)] focus:bg-surface focus:px-3 focus:py-2 focus:shadow-[var(--shadow-sm)]"
      >
        Skip to main content
      </a>
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar providerLabel={provider} providerConfigured={configured} />
        <main
          id="main-content"
          className="mx-auto w-full max-w-[var(--content-max)] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8"
        >
          {children}
        </main>
      </div>
      </div>
    </PageTitleProvider>
  );
}
