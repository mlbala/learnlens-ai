"""Optional integration probes against free-tier Neon + Qdrant Cloud.

Skipped unless DATABASE_URL, QDRANT_URL, and QDRANT_API_KEY are set.
Does not call paid AI providers.
"""

from __future__ import annotations

import os

import pytest
from app.core.settings import Settings, clear_settings_cache
from app.main import create_app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _cloud_creds_present() -> bool:
    return bool(
        os.getenv("DATABASE_URL", "").strip()
        and os.getenv("QDRANT_URL", "").strip()
        and os.getenv("QDRANT_API_KEY", "").strip()
    )


@pytest.mark.skipif(not _cloud_creds_present(), reason="Neon/Qdrant credentials not set")
def test_ready_against_cloud_services() -> None:
    clear_settings_cache()
    settings = Settings()
    app = create_app(settings)
    with TestClient(app) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 200, ready.text
        body = ready.json()
        assert body["status"] == "ok"
        assert body["checks"]["neon"]["ok"] is True
        assert body["checks"]["qdrant"]["ok"] is True
    clear_settings_cache()
