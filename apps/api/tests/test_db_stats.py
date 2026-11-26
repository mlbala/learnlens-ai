"""The request log counts database queries so slow requests can be explained."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


def _completed(caplog: pytest.LogCaptureFixture, path: str) -> logging.LogRecord:
    rows = [
        record
        for record in caplog.records
        if record.getMessage() == "request_completed" and getattr(record, "path", "") == path
    ]
    assert rows, f"no request_completed line for {path}"
    return rows[-1]


def test_request_log_counts_queries_without_sql_text(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="learnlens.request")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "db-stats@example.com", "password": "correct-horse-1", "name": "L"},
    )
    assert response.status_code == 201, response.text
    record = _completed(caplog, "/api/v1/auth/register")
    assert record.db_queries > 0
    assert record.db_ms >= 0
    assert "select" not in str(record.__dict__).lower()


def test_requests_without_database_work_count_zero(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="learnlens.request")
    assert client.get("/health/live").status_code == 200
    record = _completed(caplog, "/health/live")
    assert record.db_queries == 0
