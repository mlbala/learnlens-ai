"""Load and validate versioned golden evaluation fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.eval.paths import golden_root


class DatasetSchemaError(ValueError):
    """Golden dataset failed structural validation (hard gate)."""


class EvalTargets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    note: str = ""
    fixture_data: bool = True
    hard_gates: dict[str, Any]
    soft_targets: dict[str, float]
    # Calibrated offline gates — failing these fails `make eval` (docs/05 launch goals).
    regression_gates: dict[str, float] = Field(default_factory=dict)


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    case_type: str = Field(min_length=1)
    workspace_key: str
    workspace_id: str
    scope_kind: str = "video"
    question: str | None = None
    expected_segment_ids: list[str] = Field(default_factory=list)
    expected_answer_phrases: list[str] = Field(default_factory=list)
    should_abstain: bool = False
    no_timestamps: bool = False
    forbidden_workspace_ids: list[str] = Field(default_factory=list)
    forbidden_segment_ids: list[str] = Field(default_factory=list)

    @field_validator("workspace_id")
    @classmethod
    def _nonempty_ws(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("workspace_id required")
        return value


class GoldenDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    fixture_data: bool
    manifest: dict[str, Any]
    corpus: dict[str, Any]
    cases: list[EvalCase]
    targets: EvalTargets
    root: Path

    def video_by_key(self, key: str) -> dict[str, Any]:
        for video in self.corpus.get("videos") or []:
            if video.get("key") == key:
                return video
        raise KeyError(key)

    def playlist_by_key(self, key: str) -> dict[str, Any]:
        for playlist in self.corpus.get("playlists") or []:
            if playlist.get("key") == key:
                return playlist
        raise KeyError(key)

    def segments_for_video(self, video_key: str) -> list[dict[str, Any]]:
        return [s for s in self.corpus.get("segments") or [] if s.get("video_key") == video_key]

    def segment_by_id(self, segment_id: str) -> dict[str, Any] | None:
        for segment in self.corpus.get("segments") or []:
            if segment.get("id") == segment_id:
                return segment
        return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetSchemaError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DatasetSchemaError(f"Expected object at {path}")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatasetSchemaError(f"Cannot read {path}: {exc}") from exc
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise DatasetSchemaError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise DatasetSchemaError(f"JSONL row must be object at {path}:{line_no}")
        rows.append(row)
    return rows


def load_golden_dataset(root: Path | None = None) -> GoldenDataset:
    base = golden_root(root)
    if not base.is_dir():
        raise DatasetSchemaError(f"Golden fixture root missing: {base}")

    version_file = (base / "DATASET_VERSION").read_text(encoding="utf-8").strip()
    manifest = _read_json(base / "manifest.json")
    corpus = _read_json(base / "corpus.json")
    targets_raw = _read_json(base / "targets.json")
    cases_raw = _read_jsonl(base / "expected.jsonl")

    for name, blob in (("manifest", manifest), ("corpus", corpus), ("targets", targets_raw)):
        if blob.get("fixture_data") is False:
            raise DatasetSchemaError(f"{name} must be marked fixture_data=true")

    versions = {
        "DATASET_VERSION": version_file,
        "manifest": str(manifest.get("dataset_version") or ""),
        "corpus": str(corpus.get("dataset_version") or ""),
        "targets": str(targets_raw.get("dataset_version") or ""),
    }
    if len(set(versions.values())) != 1 or not version_file:
        raise DatasetSchemaError(f"Dataset version mismatch: {versions}")

    if not corpus.get("fixture_data"):
        raise DatasetSchemaError("corpus.json must set fixture_data=true")

    workspaces = corpus.get("workspaces") or []
    if len(workspaces) < 2:
        raise DatasetSchemaError("corpus must define at least 2 workspaces")

    playlists = corpus.get("playlists") or []
    covers = {p.get("coverage") for p in playlists}
    if "complete" not in covers or "partial" not in covers:
        raise DatasetSchemaError("corpus must include complete and partial playlists")

    segments = corpus.get("segments") or []
    if not segments:
        raise DatasetSchemaError("corpus segments cannot be empty")

    timed = any(s.get("start_ms") is not None for s in segments)
    untimed = any(s.get("timecode_quality") == "none" for s in segments)
    if not timed or not untimed:
        raise DatasetSchemaError("corpus must include timed and untimed segments")

    cases = [EvalCase.model_validate(row) for row in cases_raw]
    if not cases:
        raise DatasetSchemaError("expected.jsonl has no cases")

    targets = EvalTargets.model_validate(targets_raw)
    # Explicit fixture marker on dataset object
    return GoldenDataset(
        dataset_version=version_file,
        fixture_data=True,
        manifest=manifest,
        corpus=corpus,
        cases=cases,
        targets=targets,
        root=base,
    )
