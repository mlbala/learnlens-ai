"""Offline golden evaluation harness + full suite (fake providers only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.eval.cli import main as eval_main
from app.eval.dataset import DatasetSchemaError, load_golden_dataset
from app.eval.metrics import attribution_precision, mean_reciprocal_rank, recall_at_k
from app.eval.runner import run_eval
from app.eval.suite import run_eval_suite


def test_golden_dataset_loads_and_versions_align() -> None:
    dataset = load_golden_dataset()
    assert dataset.fixture_data is True
    assert dataset.dataset_version == "1.1.0"
    assert len(dataset.corpus["workspaces"]) >= 2
    covers = {p["coverage"] for p in dataset.corpus["playlists"]}
    assert "complete" in covers and "partial" in covers
    assert any(s.get("start_ms") is not None for s in dataset.corpus["segments"])
    assert any(s.get("timecode_quality") == "none" for s in dataset.corpus["segments"])
    assert len(dataset.cases) >= 15
    assert dataset.targets.regression_gates
    assert "attribution_precision" in dataset.targets.regression_gates


def test_metrics_recall_mrr_and_attribution() -> None:
    relevant = ["a", "b"]
    assert recall_at_k(relevant, ["a", "x", "b"], k=10) == 1.0
    assert recall_at_k(relevant, ["x", "a"], k=10) == 0.5
    assert mean_reciprocal_rank(relevant, ["x", "b"]) == pytest.approx(0.5)
    assert attribution_precision("append amortized", ["Big-O for append is amortized O(1)."]) == 1.0
    assert attribution_precision("quantum entanglement", ["append amortized"]) < 0.5


def test_eval_runner_writes_reports_and_passes_gates(tmp_path: Path) -> None:
    report = run_eval(report_dir=tmp_path / "eval")
    assert report.json_path.is_file()
    assert report.markdown_path.is_file()
    payload = json.loads(report.json_path.read_text(encoding="utf-8"))
    assert payload["fixture_data"] is True
    assert payload["dataset_version"] == "1.1.0"
    hard = payload["hard_gates"]["details"]
    assert hard["schema_valid"]["pass"] is True
    assert hard["leaked_tenant_count"]["pass"] is True
    assert hard["fabricated_timestamp_links"]["pass"] is True
    assert hard["citation_validity"]["pass"] is True
    assert hard["adversarial_exfil_blocked"]["pass"] is True
    assert hard["playlist_coverage_accuracy"]["pass"] is True
    assert payload["regression_gates"]
    assert all(row["pass"] for row in payload["regression_gates"].values())
    assert payload["scorecard"]["hard_pass"] is True
    assert "hybrid" in payload["baselines"]["retrieval"]
    assert "dense_only" in payload["baselines"]["retrieval"]
    assert payload["baselines"]["retrieval"]["hybrid_mrr_lift"] >= 0.0
    assert report.passed is True
    assert report.exit_code == 0


def test_eval_suite_all_passes(tmp_path: Path) -> None:
    report = run_eval_suite(report_dir=tmp_path / "suite")
    assert report.passed is True
    assert report.exit_code == 0
    assert (tmp_path / "suite" / "suite_report.json").is_file()
    sections = report.payload["sections"]
    assert sections["rag"]["passed"] is True
    assert sections["tutor"]["passed"] is True
    assert sections["guardrails"]["passed"] is True


def test_eval_cli_suite_exit_zero(tmp_path: Path) -> None:
    code = eval_main(["--suite", "all", "--out", str(tmp_path / "cli-out")])
    assert code == 0
    assert (tmp_path / "cli-out" / "suite_report.json").is_file()


def test_dataset_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(DatasetSchemaError):
        load_golden_dataset(tmp_path / "does-not-exist")
