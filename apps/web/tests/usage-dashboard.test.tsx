import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UsageDashboard } from "@/features/usage/usage-dashboard";

describe("UsageDashboard", () => {
  it("labels costs as estimates", () => {
    render(<UsageDashboard />);
    expect(screen.getByTestId("cost-estimate-banner")).toHaveTextContent(
      /estimates/i,
    );
    expect(screen.getByText(/not live vendor pricing/i)).toBeInTheDocument();
    expect(
      screen.getAllByText(/v0-placeholder-not-live-rates/).length,
    ).toBeGreaterThan(0);
  });
});
