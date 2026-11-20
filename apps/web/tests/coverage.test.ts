import { describe, expect, it } from "vitest";

import {
  coverageDisplayPercent,
  coverageHeadline,
  coverageLimitationCopy,
  isPartialCoverage,
  normalizeCoverage,
} from "@/lib/library/coverage";

describe("normalizeCoverage", () => {
  it("derives missing and keeps honest counts", () => {
    expect(
      normalizeCoverage({
        total: 15,
        ready: 10,
        needs_transcript: 2,
        unavailable: 1,
        failed: 2,
      }),
    ).toEqual({
      total: 15,
      ready: 10,
      needs_transcript: 2,
      unavailable: 1,
      failed: 2,
      missing: 5,
    });
  });
});

describe("partial coverage honesty", () => {
  it("marks partial when unavailable items exist", () => {
    const coverage = normalizeCoverage({
      total: 7,
      ready: 3,
      needs_transcript: 1,
      unavailable: 2,
      failed: 1,
    });
    expect(isPartialCoverage(coverage)).toBe(true);
    expect(coverageHeadline(coverage)).toBe("3 of 7 ready");
    expect(coverageDisplayPercent(coverage)).toBeLessThan(100);
    expect(coverageLimitationCopy(coverage)).toContain("unavailable");
    expect(coverageLimitationCopy(coverage)).toContain("failed");
    expect(coverageLimitationCopy(coverage)).not.toMatch(/100%/);
  });

  it("never claims full coverage copy when sources are limited", () => {
    const coverage = normalizeCoverage({
      total: 5,
      ready: 5,
      needs_transcript: 0,
      unavailable: 1,
      failed: 0,
    });
    // Impossible ready=total with unavailable>0 still treated as partial via counts.
    expect(coverageDisplayPercent(coverage)).toBeLessThan(100);
  });
});
