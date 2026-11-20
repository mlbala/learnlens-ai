"""Write JSON + Markdown evaluation reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gates = payload.get("hard_gates") or {}
    soft = payload.get("soft_metrics") or {}
    baselines = payload.get("baselines") or {}
    lines = [
        f"# LearnLens eval report — dataset {payload.get('dataset_version')}",
        "",
        f"- Generated: `{payload.get('generated_at')}`",
        f"- Fixture data: `{payload.get('fixture_data')}`",
        f"- Schema valid: `{gates.get('schema_valid')}`",
        f"- Exit: `{'PASS' if payload.get('passed') else 'FAIL'}`",
        "",
        "## Hard gates",
        "",
        "| Gate | Value | Threshold | Pass |",
        "| --- | --- | --- | --- |",
    ]
    for name, row in (gates.get("details") or {}).items():
        lines.append(
            f"| {name} | {row.get('value')} | {row.get('threshold')} | "
            f"{'yes' if row.get('pass') else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Soft quality metrics (tracked until calibrated)",
            "",
            "| Metric | Actual | Target | Meets target |",
            "| --- | --- | --- | --- |",
        ]
    )
    for name, row in soft.items():
        lines.append(
            f"| {name} | {row.get('actual')} | {row.get('target')} | "
            f"{'yes' if row.get('meets_target') else 'no'} |"
        )
    lines.extend(["", "## Baselines", ""])
    retrieval = baselines.get("retrieval") or {}
    for mode, row in retrieval.items():
        lines.append(
            f"- **{mode}**: Recall@10={row.get('recall_at_10')}, "
            f"MRR={row.get('mrr')}, latency_ms={row.get('latency_ms_mean')}"
        )
    summary = baselines.get("summarization") or {}
    for mode, row in summary.items():
        lines.append(
            f"- **summary/{mode}**: faithfulness={row.get('faithfulness')}, "
            f"coverage={row.get('coverage')}, "
            f"est_cost_usd={row.get('estimated_cost_usd')}"
        )
    failures = payload.get("gate_failures") or []
    if failures:
        lines.extend(["", "## Gate failures", ""])
        for item in failures:
            lines.append(f"- {item}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
