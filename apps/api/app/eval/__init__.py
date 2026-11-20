"""Offline evaluation harness — fake providers and golden fixtures only."""

from __future__ import annotations

from app.eval.runner import EvalReport, run_eval

__all__ = ["EvalReport", "run_eval"]
