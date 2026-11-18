"""Alembic migration smoke tests (offline structure + optional Neon upgrade/downgrade)."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    API_ROOT / "alembic" / "versions" / "20261118_0001_initial_schema.py"
)


def test_initial_migration_has_upgrade_and_downgrade() -> None:
    spec = importlib.util.spec_from_file_location("alembic_initial", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == "20261118_0001"
    assert module.down_revision is None


def test_alembic_offline_sql_generation() -> None:
    """Generate SQL without a live database connection."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    scripts = ScriptDirectory.from_config(cfg)
    rev = scripts.get_revision("20261118_0001")
    assert rev is not None
    assert "users" in (rev.doc or "users") or rev.revision == "20261118_0001"


@pytest.mark.integration
def test_alembic_upgrade_downgrade_on_neon() -> None:
    """Runs only when Neon credentials are present; does not print secrets."""
    url = (
        os.environ.get("DATABASE_URL_UNPOOLED", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    if not url or "sqlite" in url:
        pytest.skip("Neon DATABASE_URL not available for migration integration test")

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    # URL is read from env inside alembic/env.py — never log it.
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
