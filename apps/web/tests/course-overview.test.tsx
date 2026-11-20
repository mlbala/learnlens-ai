import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CourseOverview } from "@/components/library/course-overview";
import { fixturePlaylistCourseSummary } from "@/lib/library/fixtures";

describe("CourseOverview", () => {
  it("renders partial course notes and excluded lesson caveat", () => {
    const summary = fixturePlaylistCourseSummary();
    render(<CourseOverview summary={summary} />);
    expect(screen.getByText("Course overview")).toBeInTheDocument();
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(screen.getByText(/Summary covers 3 of 7 videos/)).toBeInTheDocument();
    expect(screen.getByText("Key takeaways")).toBeInTheDocument();
    expect(screen.getByText("Excluded lessons")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Copy Markdown notes/i })).toBeInTheDocument();
  });
});
