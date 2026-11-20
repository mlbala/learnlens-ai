"""Phase 14 — offline golden evaluation harness (fake providers only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.eval.cli import main as eval_main
from app.eval.dataset import DatasetSchemaError, load_golden_dataset
from app.eval.metrics import mean_reciprocal_rank, recall_at_k
from app.eval.runner import run_eval


def test_golden_dataset_loads_and_versions_align() -> None:
    dataset = load_golden_dataset()
    assert dataset.fixture_data is True
    assert dataset.dataset_version == "1.0.0"
    assert len(dataset.corpus["workspaces"]) >= 2
    covers = {p["coverage"] for p in dataset.corpus["playlists"]}
    assert "complete" in covers and "partial" in covers
    assert any(s.get("start_ms") is not None for s in dataset.corpus["segments"])
    assert any(s.get("timecode_quality") == "none" for s in dataset.corpus["segments"])
    assert len(dataset.cases) >= 10


def test_metrics_recall_and_mrr() -> None:
    relevant = ["a", "b"]
    assert recall_at_k(relevant, ["a", "x", "b"], k=10) == 1.0
    assert recall_at_k(relevant, ["x", "a"], k=10) == 0.5
    assert mean_reciprocal_rank(relevant, ["x", "b"]) == pytest.approx(0.5)


def test_eval_runner_writes_reports_and_passes_hard_gates(tmp_path: Path) -> None:
    report = run_eval(report_dir=tmp_path / "eval")
    assert report.json_path.is_file()
    assert report.markdown_path.is_file()
    payload = json.loads(report.json_path.read_text(encoding="utf-8"))
    assert payload["fixture_data"] is True
    assert payload["dataset_version"] == "1.0.0"
    hard = payload["hard_gates"]["details"]
    assert hard["schema_valid"]["pass"] is True
    assert hard["leaked_tenant_count"]["pass"] is True
    assert hard["fabricated_timestamp_links"]["pass"] is True
    assert hard["citation_validity"]["pass"] is True
    assert "hybrid" in payload["baselines"]["retrieval"]
    assert "dense_only" in payload["baselines"]["retrieval"]
    assert "naive" in payload["baselines"]["summarization"]
    assert "hierarchical" in payload["baselines"]["summarization"]
    assert report.passed is True
    assert report.exit_code == 0


def test_eval_cli_exit_zero(tmp_path: Path) -> None:
    code = eval_main(["--out", str(tmp_path / "cli-out")])
    assert code == 0
    assert (tmp_path / "cli-out" / "eval_report.json").is_file()


def test_dataset_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(DatasetSchemaError):
        load_golden_dataset(tmp_path / "does-not-exist")
