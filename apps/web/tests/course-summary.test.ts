import { describe, expect, it } from "vitest";

import { formatCourseNotesMarkdown } from "@/lib/library/course-summary";
import { fixturePlaylistCourseSummary } from "@/lib/library/fixtures";

describe("formatCourseNotesMarkdown", () => {
  it("exports partial coverage and excluded lessons without inventing content", () => {
    const summary = fixturePlaylistCourseSummary();
    const md = formatCourseNotesMarkdown(summary);
    expect(summary.coverage_label).toBe("partial");
    expect(summary.included_count).toBe(3);
    expect(summary.total_count).toBe(7);
    expect(md).toContain("partial");
    expect(md).toMatch(/Summary covers 3 of 7 videos/);
    expect(md).toContain("Excluded lessons");
    expect(md).toContain("not invented");
    for (const takeaway of summary.key_takeaways) {
      expect(takeaway.source_video_ids.length).toBeGreaterThan(0);
      expect(
        takeaway.source_video_ids.every((id) => summary.included_video_ids.includes(id)),
      ).toBe(true);
    }
  });
});
