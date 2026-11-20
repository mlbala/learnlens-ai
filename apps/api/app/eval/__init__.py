"""Offline evaluation harness — fake providers and golden fixtures only."""

from __future__ import annotations

from app.eval.runner import EvalReport, run_eval
from app.eval.suite import SuiteReport, run_eval_suite

__all__ = ["EvalReport", "SuiteReport", "run_eval", "run_eval_suite"]
