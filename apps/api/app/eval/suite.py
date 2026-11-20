"""Full offline eval suite — RAG golden + guardrails harness + tutor practice."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.eval.dataset import load_golden_dataset
from app.eval.paths import default_report_dir
from app.eval.runner import run_eval
from app.eval.tutor_eval import run_tutor_eval


@dataclass(frozen=True, slots=True)
class SuiteReport:
    payload: dict[str, Any]
    json_path: Path
    markdown_path: Path
    passed: bool
    exit_code: int


def run_eval_suite(
    *,
    dataset_root: Path | None = None,
    report_dir: Path | None = None,
    include_guardrails: bool = True,
    include_tutor: bool = True,
    include_rag: bool = True,
) -> SuiteReport:
    out = report_dir or default_report_dir()
    out.mkdir(parents=True, exist_ok=True)
    sections: dict[str, Any] = {}
    failures: list[str] = []

    if include_rag:
        rag = run_eval(dataset_root=dataset_root, report_dir=out / "rag")
        sections["rag"] = {
            "passed": rag.passed,
            "dataset_version": rag.payload.get("dataset_version"),
            "hard_gates": rag.payload.get("hard_gates"),
            "soft_metrics": rag.payload.get("soft_metrics"),
            "regression_gates": rag.payload.get("regression_gates"),
            "scorecard": rag.payload.get("scorecard"),
            "gate_failures": rag.payload.get("gate_failures") or [],
            "report_json": str(rag.json_path),
        }
        if not rag.passed:
            failures.extend(f"rag:{f}" for f in (rag.payload.get("gate_failures") or ["failed"]))

    if include_tutor:
        dataset = load_golden_dataset(dataset_root)
        tutor = run_tutor_eval(dataset)
        sections["tutor"] = tutor
        if not tutor["passed"]:
            failures.extend(f"tutor:{f}" for f in tutor.get("gate_failures") or ["failed"])

    if include_guardrails:
        from app.guardrails_harness.runner import run_guardrails_harness

        gr = run_guardrails_harness(
            report_dir=out / "guardrails",
            backend="structured",
        )
        sections["guardrails"] = {
            "passed": gr.passed,
            "case_count": gr.payload.get("case_count"),
            "passed_count": gr.payload.get("passed_count"),
            "regen_loop": gr.payload.get("regen_loop"),
            "gate_failures": gr.payload.get("gate_failures") or [],
            "report_json": str(gr.json_path),
        }
        if not gr.passed:
            failures.extend(
                f"guardrails:{f}" for f in (gr.payload.get("gate_failures") or ["failed"])
            )

    passed = len(failures) == 0
    stamp = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "suite": "learnlens_eval_suite",
        "fixture_data": True,
        "generated_at": stamp,
        "passed": passed,
        "sections": sections,
        "gate_failures": failures,
        "notes": [
            "Offline only: FakeEmbeddingAdapter + structured guardrails + tutor phrase cards.",
            "Hard RAG gates + calibrated regression gates + guardrails corpus + tutor grounding.",
            "Not a learning-efficacy claim — practice/attribution proxies only.",
        ],
    }
    json_path = out / "suite_report.json"
    md_path = out / "suite_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_lines = [
        f"# LearnLens eval suite — {stamp}",
        "",
        f"- Overall: **{'PASS' if passed else 'FAIL'}**",
        "",
        "## Sections",
        "",
    ]
    for name, section in sections.items():
        ok = section.get("passed")
        md_lines.append(f"- **{name}**: {'PASS' if ok else 'FAIL'}")
    if failures:
        md_lines.extend(["", "## Failures", ""])
        for item in failures:
            md_lines.append(f"- {item}")
    md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return SuiteReport(
        payload=payload,
        json_path=json_path,
        markdown_path=md_path,
        passed=passed,
        exit_code=0 if passed else 1,
    )
