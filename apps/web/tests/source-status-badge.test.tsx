import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceStatusBadge } from "@/components/patterns/source-status-badge";

describe("SourceStatusBadge", () => {
  it("renders accessible ready label", () => {
    render(<SourceStatusBadge status="ready" />);
    expect(screen.getByText("Ready to study")).toBeInTheDocument();
  });

  it("renders permission required for not_authorized", () => {
    render(<SourceStatusBadge status="not_authorized" />);
    expect(screen.getByText("Permission required")).toBeInTheDocument();
  });
});
