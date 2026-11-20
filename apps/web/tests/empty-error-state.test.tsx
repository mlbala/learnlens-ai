import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";

describe("EmptyState / ErrorState", () => {
  it("exposes empty status for assistive tech", () => {
    render(
      <EmptyState
        title="No sources yet"
        description="Import a permitted transcript to begin."
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("No sources yet");
  });

  it("exposes alert role for errors without leaking secrets", () => {
    render(
      <ErrorState message="Request failed. No private content is shown." />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).not.toHaveTextContent("sk-");
    expect(alert).not.toHaveTextContent("transcript");
  });
});
