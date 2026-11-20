"""Orchestrate offline golden evaluation and hard/soft/regression gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.eval.baselines import (
    OfflineIndex,
    evaluate_summary_baseline,
    scope_video_ids,
    score_retrieval,
    simulate_grounded_answer,
)
from app.eval.dataset import DatasetSchemaError, GoldenDataset, load_golden_dataset
from app.eval.metrics import hybrid_mrr_lift
from app.eval.paths import default_report_dir, golden_root
from app.eval.report import write_json_report, write_markdown_report


@dataclass(frozen=True, slots=True)
class EvalReport:
    payload: dict[str, Any]
    json_path: Path
    markdown_path: Path
    passed: bool
    exit_code: int


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def run_eval(
    *,
    dataset_root: Path | None = None,
    report_dir: Path | None = None,
) -> EvalReport:
    out_dir = report_dir or default_report_dir()
    gate_failures: list[str] = []
    schema_valid = True
    dataset: GoldenDataset | None = None

    try:
        dataset = load_golden_dataset(dataset_root)
    except DatasetSchemaError as exc:
        schema_valid = False
        gate_failures.append(f"schema_valid: {exc}")

    case_rows: list[dict[str, Any]] = []
    retrieval_hybrid: list[float] = []
    retrieval_dense: list[float] = []
    mrr_hybrid: list[float] = []
    mrr_dense: list[float] = []
    latency_hybrid: list[float] = []
    latency_dense: list[float] = []
    abstention_hits = 0
    abstention_total = 0
    completeness_scores: list[float] = []
    attribution_scores: list[float] = []
    citation_case_pass = 0
    citation_case_total = 0
    leaked_tenant_count = 0
    fabricated_timestamp_links = 0
    exfil_failures = 0
    playlist_coverage_pass = 0
    playlist_coverage_total = 0
    summary_naive: dict[str, float] | None = None
    summary_hier: dict[str, float] | None = None

    if dataset is not None:
        index = OfflineIndex(dataset)
        for case_model in dataset.cases:
            case = case_model.model_dump()
            case_type = str(case.get("case_type") or "")

            if case_type == "playlist_coverage":
                playlist = dataset.playlist_by_key(str(case.get("scope_playlist_key")))
                ready = [
                    k
                    for k in (playlist.get("member_video_keys") or [])
                    if dataset.video_by_key(str(k)).get("transcript_ready")
                ]
                missing = [
                    k
                    for k in (playlist.get("member_video_keys") or [])
                    if not dataset.video_by_key(str(k)).get("transcript_ready")
                ]
                ratio = len(ready) / max(1, len(playlist.get("member_video_keys") or []))
                expected_raw = case.get("expected_coverage_ratio")
                if expected_raw is None:
                    expected_raw = playlist.get("expected_coverage_ratio") or 0
                expected = float(expected_raw)
                ok = abs(ratio - expected) < 1e-6 and set(missing) == set(
                    case.get("excluded_video_keys") or []
                )
                playlist_coverage_total += 1
                if ok:
                    playlist_coverage_pass += 1
                else:
                    gate_failures.append(f"playlist_coverage:{case['id']}")
                case_rows.append(
                    {
                        "id": case["id"],
                        "case_type": case_type,
                        "coverage_ratio": ratio,
                        "expected_coverage_ratio": expected,
                        "pass": ok,
                    }
                )
                continue

            if case_type == "summary":
                naive = evaluate_summary_baseline(dataset, case, mode="naive")
                hier = evaluate_summary_baseline(dataset, case, mode="hierarchical")
                summary_naive = {
                    "faithfulness": naive.faithfulness,
                    "coverage": naive.coverage,
                    "latency_ms": naive.latency_ms,
                    "estimated_cost_usd": naive.estimated_cost_usd,
                }
                summary_hier = {
                    "faithfulness": hier.faithfulness,
                    "coverage": hier.coverage,
                    "latency_ms": hier.latency_ms,
                    "estimated_cost_usd": hier.estimated_cost_usd,
                    "dropped_citation_ids": len(hier.dropped_citation_ids),
                }
                citation_case_total += 1
                if hier.dropped_citation_ids:
                    citation_case_pass += 1
                else:
                    gate_failures.append(f"citation_validity:summary:{case['id']}")
                case_rows.append(
                    {
                        "id": case["id"],
                        "case_type": case_type,
                        "naive": summary_naive,
                        "hierarchical": summary_hier,
                    }
                )
                continue

            video_ids = scope_video_ids(dataset, case)
            question = str(case.get("question") or "")
            relevant = list(case.get("expected_segment_ids") or [])

            hybrid_raw = index.search(
                question=question,
                workspace_id=str(case["workspace_id"]),
                video_ids=video_ids,
                dense_only=False,
                forbidden_workspace_ids=list(case.get("forbidden_workspace_ids") or []),
            )
            dense_raw = index.search(
                question=question,
                workspace_id=str(case["workspace_id"]),
                video_ids=video_ids,
                dense_only=True,
                forbidden_workspace_ids=list(case.get("forbidden_workspace_ids") or []),
            )
            hybrid = score_retrieval(hybrid_raw, relevant)
            dense = score_retrieval(dense_raw, relevant)
            leaked_tenant_count += hybrid.leaked_tenant_count + dense.leaked_tenant_count

            if relevant and not case.get("should_abstain"):
                retrieval_hybrid.append(hybrid.recall_at_10)
                retrieval_dense.append(dense.recall_at_10)
                mrr_hybrid.append(hybrid.mrr)
                mrr_dense.append(dense.mrr)
            latency_hybrid.append(hybrid.latency_ms)
            latency_dense.append(dense.latency_ms)

            qa = simulate_grounded_answer(dataset, case, hybrid.retrieved_segment_ids)
            leaked_tenant_count += int(qa["leaked_tenant_count"])
            fabricated_timestamp_links += int(qa["fabricated_timestamp_links"])

            if case.get("must_not_exfiltrate") and not qa.get("exfil_blocked", True):
                exfil_failures += 1
                gate_failures.append(f"adversarial_exfil:{case['id']}")

            if case.get("should_abstain"):
                abstention_total += 1
                if qa["refused"]:
                    abstention_hits += 1

            completeness_scores.append(float(qa["answer_completeness"]))
            if not case.get("should_abstain"):
                attribution_scores.append(float(qa.get("attribution_precision") or 0.0))

            citation_case_total += 1
            cited_ok = all(
                sid in set(hybrid.retrieved_segment_ids) or case.get("should_abstain")
                for sid in qa["cited_segment_ids"]
            )
            if case_type == "citation_gate":
                fabricated = "00000000-0000-4000-8000-00000000dead"
                dropped_ok = fabricated in set(qa["dropped_citation_ids"])
                kept_clean = fabricated not in set(qa["cited_segment_ids"])
                if dropped_ok and kept_clean:
                    citation_case_pass += 1
                else:
                    gate_failures.append(f"citation_validity:{case['id']}")
            elif case_type == "security_tenant":
                foreign = set(case.get("injected_foreign_segment_ids") or [])
                cited = set(qa["cited_segment_ids"])
                tenant_ok = foreign.isdisjoint(cited) and qa["leaked_tenant_count"] == 0
                if tenant_ok:
                    citation_case_pass += 1
                else:
                    gate_failures.append(f"citation_validity_tenant:{case['id']}")
                    leaked_tenant_count += 1
            elif cited_ok:
                citation_case_pass += 1
            else:
                gate_failures.append(f"citation_validity:{case['id']}")

            if case.get("no_timestamps") and qa["fabricated_timestamp_links"]:
                gate_failures.append(f"fabricated_timestamp_links:{case['id']}")

            case_rows.append(
                {
                    "id": case["id"],
                    "case_type": case_type,
                    "retrieval": {
                        "hybrid": {
                            "recall_at_10": hybrid.recall_at_10,
                            "mrr": hybrid.mrr,
                            "latency_ms": hybrid.latency_ms,
                            "retrieved_segment_ids": hybrid.retrieved_segment_ids,
                        },
                        "dense_only": {
                            "recall_at_10": dense.recall_at_10,
                            "mrr": dense.mrr,
                            "latency_ms": dense.latency_ms,
                            "retrieved_segment_ids": dense.retrieved_segment_ids,
                        },
                    },
                    "qa": {
                        "refused": qa["refused"],
                        "cited_segment_ids": qa["cited_segment_ids"],
                        "dropped_citation_ids": qa["dropped_citation_ids"],
                        "answer_completeness": qa["answer_completeness"],
                        "attribution_precision": qa.get("attribution_precision"),
                        "exfil_blocked": qa.get("exfil_blocked"),
                        "citation_links": qa["citation_links"],
                    },
                }
            )

    citation_validity = (
        1.0 if citation_case_total == 0 else citation_case_pass / citation_case_total
    )
    playlist_coverage_accuracy = (
        1.0
        if playlist_coverage_total == 0
        else playlist_coverage_pass / playlist_coverage_total
    )
    hard = {
        "citation_validity": {
            "value": citation_validity,
            "threshold": 1.0,
            "pass": citation_validity >= 1.0,
        },
        "leaked_tenant_count": {
            "value": leaked_tenant_count,
            "threshold": 0,
            "pass": leaked_tenant_count == 0,
        },
        "fabricated_timestamp_links": {
            "value": fabricated_timestamp_links,
            "threshold": 0,
            "pass": fabricated_timestamp_links == 0,
        },
        "adversarial_exfil_blocked": {
            "value": exfil_failures,
            "threshold": 0,
            "pass": exfil_failures == 0,
        },
        "playlist_coverage_accuracy": {
            "value": playlist_coverage_accuracy,
            "threshold": 1.0,
            "pass": playlist_coverage_accuracy >= 1.0,
        },
        "schema_valid": {
            "value": schema_valid,
            "threshold": True,
            "pass": schema_valid,
        },
    }
    for name, row in hard.items():
        if not row["pass"]:
            gate_failures.append(f"{name}={row['value']}")

    soft_targets = dataset.targets.soft_targets if dataset else {}
    regression_targets = dataset.targets.regression_gates if dataset else {}
    hybrid_recall = _mean(retrieval_hybrid)
    hybrid_mrr = _mean(mrr_hybrid)
    dense_mrr = _mean(mrr_dense)
    soft_actual = {
        "retrieval_recall_at_10": hybrid_recall,
        "retrieval_mrr": hybrid_mrr,
        "abstention_accuracy": (
            1.0 if abstention_total == 0 else abstention_hits / abstention_total
        ),
        "summarization_faithfulness": (summary_hier or {}).get("faithfulness", 0.0),
        "summarization_coverage": (summary_hier or {}).get("coverage", 0.0),
        "answer_completeness": _mean(completeness_scores),
        "attribution_precision": _mean(attribution_scores),
        "hybrid_mrr_lift": hybrid_mrr_lift(hybrid_mrr=hybrid_mrr, dense_mrr=dense_mrr),
        "playlist_coverage_accuracy": playlist_coverage_accuracy,
    }
    soft_metrics = {
        name: {
            "actual": round(float(actual), 4),
            "target": soft_targets.get(name),
            "meets_target": (
                soft_targets.get(name) is not None and float(actual) >= float(soft_targets[name])
            ),
        }
        for name, actual in soft_actual.items()
    }

    regression_gates: dict[str, Any] = {}
    for name, threshold in regression_targets.items():
        actual = float(soft_actual.get(name, 0.0))
        ok = actual >= float(threshold)
        regression_gates[name] = {
            "actual": round(actual, 4),
            "threshold": float(threshold),
            "pass": ok,
        }
        if not ok:
            gate_failures.append(f"regression:{name}={actual}<{threshold}")

    scorecard = {
        "cases": len(case_rows),
        "hard_pass": all(row["pass"] for row in hard.values()),
        "regression_pass": all(row["pass"] for row in regression_gates.values())
        if regression_gates
        else True,
        "soft_met_count": sum(1 for row in soft_metrics.values() if row.get("meets_target")),
        "soft_total": len(soft_metrics),
        "hybrid_beats_dense_mrr": soft_actual["hybrid_mrr_lift"] >= 0.0,
    }

    passed = (
        schema_valid
        and not gate_failures
        and all(row["pass"] for row in hard.values())
        and all(row["pass"] for row in regression_gates.values())
    )
    payload: dict[str, Any] = {
        "dataset_version": dataset.dataset_version if dataset else None,
        "fixture_data": True,
        "dataset_root": str(golden_root(dataset_root)),
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": passed,
        "scorecard": scorecard,
        "hard_gates": {"details": hard, "schema_valid": schema_valid},
        "soft_metrics": soft_metrics,
        "regression_gates": regression_gates,
        "baselines": {
            "retrieval": {
                "hybrid": {
                    "recall_at_10": round(_mean(retrieval_hybrid), 4),
                    "mrr": round(_mean(mrr_hybrid), 4),
                    "latency_ms_mean": round(_mean(latency_hybrid), 4),
                },
                "dense_only": {
                    "recall_at_10": round(_mean(retrieval_dense), 4),
                    "mrr": round(_mean(mrr_dense), 4),
                    "latency_ms_mean": round(_mean(latency_dense), 4),
                },
                "hybrid_mrr_lift": round(float(soft_actual["hybrid_mrr_lift"]), 4),
            },
            "summarization": {
                "naive": summary_naive or {},
                "hierarchical": summary_hier or {},
            },
        },
        "case_results": case_rows,
        "gate_failures": gate_failures,
        "notes": [
            "Soft metrics are tracked; regression_gates are calibrated offline fail-closed gates.",
            "Hard gates: leaks, fabricated timestamps, schema, citation validity, "
            "playlist coverage, adversarial exfil.",
            "Attribution precision is a lexical proxy — not human entailment.",
            "Providers: FakeEmbeddingAdapter + InMemoryVectorStore only (no paid API calls).",
        ],
    }

    json_path = out_dir / "eval_report.json"
    md_path = out_dir / "eval_report.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)
    return EvalReport(
        payload=payload,
        json_path=json_path,
        markdown_path=md_path,
        passed=passed,
        exit_code=0 if passed else 1,
    )
