/**
 * Course / playlist synthesis helpers — fixture-safe Markdown export.
 * Never invents coverage for missing lessons.
 */

import type { PlaylistCourseSummary } from "@/lib/library/types";

export function formatCourseNotesMarkdown(summary: PlaylistCourseSummary): string {
  const lines: string[] = [];
  lines.push(`# ${escapeMd(summary.overview.split("\n")[0] || "Course notes")}`);
  lines.push("");
  lines.push(
    `> ${escapeMd(summary.caveat || `Summary covers ${summary.included_count} of ${summary.total_count} videos`)}`,
  );
  lines.push("");
  lines.push(`Coverage: **${summary.coverage_label}** (${summary.included_count}/${summary.total_count})`);
  lines.push("");
  lines.push("## Overview");
  lines.push(escapeMd(summary.overview));
  lines.push("");

  if (summary.topic_modules.length) {
    lines.push("## Topic modules");
    for (const mod of summary.topic_modules) {
      lines.push(`### ${escapeMd(mod.title)}`);
      lines.push(escapeMd(mod.summary));
      lines.push(`Sources: ${mod.video_ids.map(escapeMd).join(", ") || "none"}`);
      lines.push("");
    }
  }

  if (summary.learning_map.length) {
    lines.push("## Learning map");
    for (const node of [...summary.learning_map].sort((a, b) => a.order - b.order)) {
      lines.push(`- ${escapeMd(node.label)} (${node.video_ids.map(escapeMd).join(", ")})`);
    }
    lines.push("");
  }

  if (summary.cross_video_concepts.length) {
    lines.push("## Cross-video concepts");
    for (const concept of summary.cross_video_concepts) {
      lines.push(`### ${escapeMd(concept.name)}`);
      lines.push(escapeMd(concept.description));
      lines.push(`Videos: ${concept.video_ids.map(escapeMd).join(", ")}`);
      lines.push("");
    }
  }

  if (summary.redundant_topics.length) {
    lines.push("## Redundant topics");
    for (const group of summary.redundant_topics) {
      lines.push(
        `- **${escapeMd(group.topic)}** — ${escapeMd(group.note || "Repeated across ready lessons")} (${group.video_ids.map(escapeMd).join(", ")})`,
      );
    }
    lines.push("");
  }

  if (summary.key_takeaways.length) {
    lines.push("## Key takeaways");
    for (const takeaway of summary.key_takeaways) {
      lines.push(
        `- ${escapeMd(takeaway.text)} _(videos: ${takeaway.source_video_ids.map(escapeMd).join(", ") || "n/a"})_`,
      );
    }
    lines.push("");
  }

  if (summary.excluded_video_ids.length) {
    lines.push("## Excluded lessons");
    lines.push(
      "The following items were not synthesized (missing transcript or unavailable). No content was invented for them:",
    );
    for (const id of summary.excluded_video_ids) {
      lines.push(`- ${escapeMd(id)}`);
    }
    lines.push("");
  }

  if (summary.fixture_data) {
    lines.push("_Synthetic fixture data — not live YouTube content._");
  }

  return lines.join("\n");
}

function escapeMd(value: string): string {
  return value.replace(/[\\`*_{}[\]()#+\-.!|]/g, "\\$&");
}
