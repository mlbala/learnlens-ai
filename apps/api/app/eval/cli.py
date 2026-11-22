"""CLI entry for offline evaluation (`python -m app.eval.cli` / `make eval`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.eval.runner import run_eval
from app.eval.suite import run_eval_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="learnlens-eval",
        description="Run LearnLens offline evaluation suites (fake providers only).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to fixtures/golden (default: monorepo fixtures/golden)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Report output directory (default: artifacts/eval)",
    )
    parser.add_argument(
        "--suite",
        choices=("all", "rag", "guardrails", "tutor"),
        default="all",
        help="Which suite to run (default: all = RAG + tutor + guardrails)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.suite == "rag":
        report = run_eval(dataset_root=args.dataset, report_dir=args.out)
        label = "eval"
    elif args.suite == "all":
        report = run_eval_suite(
            dataset_root=args.dataset,
            report_dir=args.out,
            include_rag=True,
            include_tutor=True,
            include_guardrails=True,
            include_judge=True,
        )
        label = "eval-suite"
    elif args.suite == "tutor":
        report = run_eval_suite(
            dataset_root=args.dataset,
            report_dir=args.out,
            include_rag=False,
            include_tutor=True,
            include_guardrails=False,
            include_judge=False,
        )
        label = "eval-tutor"
    else:
        report = run_eval_suite(
            dataset_root=args.dataset,
            report_dir=args.out,
            include_rag=False,
            include_tutor=False,
            include_guardrails=True,
            include_judge=False,
        )
        label = "eval-guardrails"

    status = "PASS" if report.passed else "FAIL"
    print(f"{label} {status}")
    print(f"json: {report.json_path}")
    print(f"markdown: {report.markdown_path}")
    failures = report.payload.get("gate_failures") or []
    if failures:
        print("gate_failures:")
        for item in failures:
            print(f"  - {item}")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
