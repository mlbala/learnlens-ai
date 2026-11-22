"""Load security injection corpus for the guardrails harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CorpusCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    category: str
    text: str
    expect: str
    # harness extensions (optional in legacy rows)
    channel: str = "evidence_indirect"
    expected_verdict: str | None = None
    # When true, a single regen loop must clear unsafe model output.
    regen_loop: bool = False


class CorpusFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[CorpusCase] = Field(default_factory=list)


def default_corpus_path() -> Path:
    from app.core.paths import repo_root

    return repo_root() / "fixtures" / "security" / "injection_corpus.jsonl"


def load_corpus(path: Path | None = None) -> list[CorpusCase]:
    file_path = path or default_corpus_path()
    rows: list[CorpusCase] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw: dict[str, Any] = json.loads(line)
        # Infer channel/verdict for legacy rows.
        expect = str(raw.get("expect") or "")
        if "channel" not in raw:
            if expect in {"treated_as_data", "no_outbound_fetch", "escaped_or_stripped"}:
                raw["channel"] = "evidence_indirect"
                raw.setdefault("expected_verdict", "quarantine")
            elif expect == "block_direct":
                raw["channel"] = "user_direct"
                raw.setdefault("expected_verdict", "block")
            elif expect == "allow":
                raw["channel"] = "user_direct"
                raw.setdefault("expected_verdict", "allow")
            else:
                raw["channel"] = "evidence_indirect"
                raw.setdefault("expected_verdict", "quarantine")
        rows.append(CorpusCase.model_validate(raw))
    return rows
