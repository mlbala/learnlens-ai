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
    assert sections["judge"]["passed"] is True
    assert sections["judge"]["failing_cases"] == [
        "paper_claim_after_search_off",
        "invented_timestamp",
    ]
    assert "relevance" not in sections["judge"]["hard_gates"]


def test_eval_cli_suite_exit_zero(tmp_path: Path) -> None:
    code = eval_main(["--suite", "all", "--out", str(tmp_path / "cli-out")])
    assert code == 0
    assert (tmp_path / "cli-out" / "suite_report.json").is_file()


def test_dataset_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(DatasetSchemaError):
        load_golden_dataset(tmp_path / "does-not-exist")


def test_judge_cases_score_faithfulness_by_origin() -> None:
    from app.eval.judge_eval import (
        PAPER_TEXT,
        VIDEO_TEXT,
        load_judge_cases,
        render_judge_input,
        request_for_case,
        run_judge_eval,
    )
    from app.services.session_judge import score_rubric

    report = run_judge_eval()
    assert report["passed"] is True
    assert report["judge"] == "fixture"
    by_id = {row["id"]: row for row in report["cases"]}
    follow = by_id["followup_lesson_panel"]
    paper = by_id["paper_claim_after_search_off"]
    invented = by_id["invented_timestamp"]
    abstain = by_id["abstain_search_off"]
    blend = by_id["blend_kept_urls"]
    assert follow["passed"] is True
    assert follow["faithfulness"] == 1.0
    assert follow["allowed_origins"] == ["video_transcript"]
    assert paper["passed"] is False
    assert paper["faithfulness"] == 0.0
    assert paper["thread_id"] == follow["thread_id"]
    assert paper["external_search"] is False
    assert invented["passed"] is False
    assert invented["fabricated_timestamp"] is True
    assert abstain["faithfulness"] == 1.0
    assert abstain["source_precision"] == 1.0
    assert blend["faithfulness"] == 1.0
    assert blend["source_precision"] == 1.0
    assert blend["allowed_origins"] == ["video_transcript", "external_search"]
    assert report["hard_gates"]["leaked_tenant_count"]["pass"] is True
    assert report["hard_gates"]["fabricated_timestamp_on_clean_cases"]["pass"] is True
    assert report["soft_metrics"]["relevance"]["gated"] is False
    assert report["soft_metrics"]["relevance"]["by_case"] == {
        "followup_lesson_panel": 1.0,
        "abstain_search_off": 1.0,
        "blend_kept_urls": 1.0,
        "paper_claim_after_search_off": 0.0,
        "invented_timestamp": 1.0,
    }

    cases = {case.id: case for case in load_judge_cases()}
    follow_case = cases["followup_lesson_panel"]
    paper_case = cases["paper_claim_after_search_off"]
    assert follow_case.earlier_decision == "blend"
    assert paper_case.earlier_decision == "blend"
    assert follow_case.thread_id == paper_case.thread_id
    follow_rendered = render_judge_input(request_for_case(follow_case))
    follow_passages = follow_rendered.split("DRAFT:", 1)[0]
    assert follow_case.earlier_lesson_panel in follow_passages
    assert VIDEO_TEXT in follow_passages
    assert PAPER_TEXT not in follow_rendered
    assert follow_case.earlier_external_panel not in follow_passages
    paper_rendered = render_judge_input(request_for_case(paper_case))
    paper_passages, _, paper_draft = paper_rendered.partition("DRAFT:")
    assert PAPER_TEXT not in paper_passages
    assert PAPER_TEXT in paper_draft
    assert score_rubric(request_for_case(follow_case)).faithfulness == 1.0
    assert score_rubric(request_for_case(paper_case)).faithfulness == 0.0
    assert "FOREIGN_TENANT_YIELD_SECRET" not in follow_rendered
    assert "FOREIGN_TENANT_YIELD_SECRET" not in paper_rendered


def test_swapped_judge_that_misses_failures_fails_the_suite() -> None:
    from app.eval.judge_eval import run_judge_eval
    from app.services.session_judge import JudgeScore

    def blind(request: object) -> JudgeScore:
        del request
        return JudgeScore(1.0, 1.0, 1.0, False)

    report = run_judge_eval(judge=blind)
    assert report["judge"] == "swapped"
    assert report["passed"] is False
    assert "invented_timestamp_not_detected" in report["gate_failures"]
    assert "paper_claim_after_search_off_faithfulness" in report["gate_failures"]


def test_relevance_is_not_a_new_hard_gate() -> None:
    root = Path(__file__).resolve().parents[3]
    targets_path = root / "fixtures" / "golden" / "targets.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    assert "relevance" not in targets["hard_gates"]
    assert "judge_relevance" not in targets["hard_gates"]
    assert "relevance" not in targets["regression_gates"]


def test_docker_build_does_not_need_the_eval_suite() -> None:
    workflow = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text(encoding="utf-8")
    docker = text.split("docker-build:", 1)[1].split("steps:", 1)[0]
    assert "needs: [quality, security-guardrails]" in docker
    assert "eval-suite" not in docker


def test_score_is_not_required_in_the_web_bundle() -> None:
    root = Path(__file__).resolve().parents[3] / "apps" / "web"
    files = [
        root / "components" / "lesson" / "answer-view.tsx",
        root / "components" / "lesson" / "chat-panel.tsx",
        root / "lib" / "lesson" / "answer.ts",
    ]
    blob = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "faithfulness" not in blob
    assert "source_precision" not in blob
    assert "judge score" not in blob.lower()
