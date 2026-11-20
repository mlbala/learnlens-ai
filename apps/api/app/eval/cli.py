"""CLI entry for offline evaluation (`python -m app.eval.cli` / `make eval`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.eval.runner import run_eval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="learnlens-eval",
        description="Run LearnLens offline golden evaluation (fake providers only).",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_eval(dataset_root=args.dataset, report_dir=args.out)
    status = "PASS" if report.passed else "FAIL"
    print(f"eval {status}")
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
