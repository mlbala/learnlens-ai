"""CLI: `python -m app.guardrails_harness.cli` / `make guardrails-harness`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.guardrails_harness.runner import run_guardrails_harness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="learnlens-guardrails-harness",
        description="Offline guardrails corpus + regen-loop harness (fake/structured).",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Path to injection_corpus.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Report directory (default: artifacts/guardrails)",
    )
    parser.add_argument(
        "--backend",
        default="structured",
        choices=("structured", "nemo", "hf"),
        help="Scanner backend (default: structured for offline CI)",
    )
    parser.add_argument(
        "--max-regen-loops",
        type=int,
        default=1,
        help="Max output regeneration loops under test (default: 1)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_guardrails_harness(
        corpus_path=args.corpus,
        report_dir=args.out,
        backend=args.backend,
        max_regen_loops=args.max_regen_loops,
    )
    status = "PASS" if report.passed else "FAIL"
    print(f"guardrails-harness {status}")
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
