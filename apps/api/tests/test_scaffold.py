"""Minimal offline unit tests for scaffolding helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.scaffold import project_slug
from app.core.settings import Settings


def test_project_slug_normalizes_display_name() -> None:
    assert project_slug("LearnLens AI") == "learnlens-ai"


def test_project_slug_rejects_empty() -> None:
    with pytest.raises(ValueError, match="alphanumeric"):
        project_slug("   ---   ")


def test_settings_default_to_fake_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    # Assert field defaults, not whatever a local .env or shell exported.
    monkeypatch.delenv("AI_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("AI_EMBED_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ai_chat_provider == "fake"
    assert settings.ai_embed_provider == "fake"


def test_settings_env_files_stay_inside_repo() -> None:
    env_files = Settings.model_config.get("env_file")
    assert isinstance(env_files, tuple)
    repo_root = Path(__file__).resolve().parents[3]
    for path in env_files:
        resolved = Path(path).resolve()
        assert repo_root in resolved.parents or resolved.parent == repo_root
        assert ".." not in Path(path).parts
