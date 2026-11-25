import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppTopbar } from "@/components/shell/app-topbar";
import { PageTitleProvider } from "@/components/shell/page-title";
import { videosSearchHref } from "@/lib/library/search-href";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push }),
}));
vi.mock("@/components/shell/theme-toggle", () => ({ ThemeToggle: () => null }));
vi.mock("@/components/shell/mobile-nav", () => ({ MobileNav: () => null }));

function renderTopbar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PageTitleProvider>
        <AppTopbar />
      </PageTitleProvider>
    </QueryClientProvider>,
  );
}

describe("Header search", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            user: { email: "learner@example.com", display_name: "Learner" },
            workspace: { name: "Learner's workspace" },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("writes the title query onto /videos", () => {
    renderTopbar();
    const input = screen.getByRole("searchbox", { name: "Search lesson titles" });
    expect(input).toBeEnabled();
    fireEvent.change(input, { target: { value: "  Photosynthesis basics " } });
    fireEvent.submit(input.closest("form")!);
    expect(push).toHaveBeenCalledWith("/videos?q=Photosynthesis%20basics");
  });

  it("clears q on an empty submit", () => {
    renderTopbar();
    const input = screen.getByRole("searchbox", { name: "Search lesson titles" });
    fireEvent.submit(input.closest("form")!);
    expect(push).toHaveBeenCalledWith("/videos");
    expect(videosSearchHref("   ")).toBe("/videos");
  });

  it("shows the signed-in email from /api/me", async () => {
    renderTopbar();
    expect(await screen.findByText("learner@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
