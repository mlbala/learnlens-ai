"""Phase 15 — observability, quotas, cost estimates, circuit/DLQ (offline)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import anyio
import pytest
from app.ai.errors import ProviderTemporarilyUnavailable
from app.ai.retry import with_bounded_retry
from app.core.observability.circuit_breaker import (
    CircuitOpenError,
    configure_circuit_breaker,
    get_circuit_breaker,
)
from app.core.observability.cost import (
    COST_ESTIMATE_VERSION,
    estimate_provider_cost,
)
from app.core.observability.dead_letter import evaluate_retry
from app.core.observability.error_taxonomy import classify_error
from app.core.observability.job_recovery import recover_expired_leases
from app.core.observability.logging import JsonLogFormatter
from app.core.observability.sanitize import sanitize_span_attributes
from app.core.observability.tracing import (
    bind_context,
    clear_context,
    recent_spans_for_tests,
    reset_spans_for_tests,
    start_span,
)
from app.core.settings import Settings
from app.db.models import IngestionJob
from app.db.models.usage import UsageLimit
from app.db.seed import seed_fixture_video
from app.services.usage import UsageService, current_period
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import TEST_PASSWORD, auth_csrf_headers

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


@pytest.fixture(autouse=True)
def _reset_obs() -> None:
    reset_spans_for_tests()
    configure_circuit_breaker(failure_threshold=3, recovery_timeout_seconds=60.0)
    get_circuit_breaker().reset()
    yield
    clear_context()
    reset_spans_for_tests()
    get_circuit_breaker().reset()


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "name": "Obs"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_video(client: TestClient, settings: Settings, workspace_id: uuid.UUID) -> uuid.UUID:
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _run() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_id,
                youtube_video_id=f"fixtureObs{uuid.uuid4().hex[:8]}",
                title="Fixture video for observability tests (synthetic)",
            )
            await session.commit()
            return video_id

    return anyio.run(_run)


def test_spans_never_include_transcript_or_api_keys() -> None:
    with start_span(
        "unit.sanitize",
        transcript="SECRET CUE TEXT SHOULD DROP",
        api_key="sk-should-never-appear-xxxxxxxx",
        job_id="abc-123",
        cue_text="also dropped",
    ) as span:
        span.set_attribute("prompt", "system secret")
        span.set_attribute("video_id", str(uuid.uuid4()))
    spans = recent_spans_for_tests()
    assert spans
    attrs = spans[-1]["attributes"]
    blob = json.dumps(attrs)
    assert "SECRET CUE" not in blob
    assert "sk-should-never" not in blob
    assert "cue_text" not in attrs
    assert "transcript" not in attrs
    assert "api_key" not in attrs
    assert "prompt" not in attrs
    assert "job_id" in attrs


def test_sanitize_redacts_long_tokens() -> None:
    cleaned = sanitize_span_attributes(
        {"note": "bearer FAKESECRET_i3j4k5l6m7n8o9p0q1r2", "count": 3}
    )
    assert cleaned["count"] == 3
    assert "REDACTED" in cleaned["note"]


def test_json_log_formatter_includes_request_id() -> None:
    bind_context(request_id="req-1", trace_id="a" * 32)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    line = JsonLogFormatter().format(record)
    payload = json.loads(line)
    assert payload["request_id"] == "req-1"
    assert payload["trace_id"] == "a" * 32
    assert payload["message"] == "hello"


def test_cost_estimate_is_versioned_and_fake_is_zero() -> None:
    est = estimate_provider_cost(
        provider="fake", model="fake-chat-v1", token_in=1000, token_out=500
    )
    assert est.is_estimate is True
    assert est.estimate_version == COST_ESTIMATE_VERSION
    assert est.estimate_usd == 0.0
    assert "not live" in est.disclaimer.lower()


def test_error_taxonomy_marks_provider_outage_actionable() -> None:
    meta = classify_error("PROVIDER_TEMPORARILY_UNAVAILABLE")
    assert meta["category"] == "provider"
    assert meta["actionable"] is True


def test_dead_letter_after_retries_exhausted() -> None:
    decision = evaluate_retry(
        attempt=3,
        max_attempts=3,
        error_code="PROVIDER_TEMPORARILY_UNAVAILABLE",
        retryable=True,
    )
    assert decision.dead_letter is True
    assert decision.error_code == "JOB_DEAD_LETTER"
    assert decision.taxonomy["actionable"] is True


def test_circuit_breaker_opens_on_repeated_outage() -> None:
    configure_circuit_breaker(failure_threshold=2, recovery_timeout_seconds=60.0)
    breaker = get_circuit_breaker()

    async def boom() -> None:
        raise ProviderTemporarilyUnavailable("simulated outage", provider="fake")

    async def run() -> None:
        with pytest.raises(ProviderTemporarilyUnavailable):
            await with_bounded_retry(boom, max_retries=0, provider="fake")
        with pytest.raises(ProviderTemporarilyUnavailable):
            await with_bounded_retry(boom, max_retries=0, provider="fake")
        with pytest.raises(CircuitOpenError):
            await with_bounded_retry(boom, max_retries=0, provider="fake")

    anyio.run(run)
    assert breaker.is_open("fake")


def test_health_live_returns_trace_headers(client: TestClient) -> None:
    res = client.get("/health/live", headers={"X-Request-ID": "manual-req-1"})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == "manual-req-1"
    assert res.headers.get("X-Trace-ID")
    assert res.json()["request_id"] == "manual-req-1"


def test_usage_endpoint_labels_estimates(client: TestClient) -> None:
    _register(client, "usage-obs@example.com")
    res = client.get("/api/v1/usage")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["estimated_cost"]["is_estimate"] is True
    assert body["estimated_cost"]["estimate_version"] == COST_ESTIMATE_VERSION
    assert "not live" in body["estimated_cost"]["disclaimer"].lower()
    assert "quotas" in body
    assert body["period"] == current_period()


def test_workspace_quota_blocks_jobs(client: TestClient, settings: Settings) -> None:
    body = _register(client, "quota-jobs@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)

    async def _cap() -> None:
        async with client.app.state.session_factory() as session:
            svc = UsageService(session, client.app.state.settings)
            row = await svc._row(workspace_id)
            row.jobs_cap = 1
            row.jobs_used = 1
            await session.commit()

    anyio.run(_cap)

    srt = (FIXTURES / "sample.srt").read_bytes()
    up = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers={**auth_csrf_headers(client), "Idempotency-Key": "quota-block-1"},
        data={"rights_attested": "true", "source_kind": "srt"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    assert up.status_code == 429, up.text
    assert up.json()["error"]["code"] in {
        "WORKSPACE_JOB_QUOTA_EXCEEDED",
        "USAGE_QUOTA_EXCEEDED",
    }


def test_repeated_provider_effect_key_does_not_double_spend(client: TestClient) -> None:
    body = _register(client, "double-spend@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])

    async def _run() -> tuple[float, float]:
        async with client.app.state.session_factory() as session:
            svc = UsageService(session, client.app.state.settings)
            seen: set[str] = set()
            await svc.record_provider_usage(
                workspace_id,
                token_in=100,
                token_out=50,
                estimate_usd=0.01,
                effect_key="hash-1",
                seen_effect_keys=seen,
            )
            first = float((await svc._row(workspace_id)).estimated_spend_usd)
            again = await svc.record_provider_usage(
                workspace_id,
                token_in=100,
                token_out=50,
                estimate_usd=0.01,
                effect_key="hash-1",
                seen_effect_keys=seen,
            )
            assert again is False
            second = float((await svc._row(workspace_id)).estimated_spend_usd)
            await session.commit()
            return first, second

    first, second = anyio.run(_run)
    assert first == pytest.approx(0.01)
    assert second == pytest.approx(0.01)


def test_idempotent_transcript_replay_does_not_double_job_count(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    from app.core.settings import clear_settings_cache

    clear_settings_cache()
    body = _register(client, "idem-jobs@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    video_id = _seed_video(client, settings, workspace_id)
    srt = (FIXTURES / "sample.srt").read_bytes()
    headers = {**auth_csrf_headers(client), "Idempotency-Key": "idem-obs-1"}
    first = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true", "source_kind": "srt"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    assert first.status_code == 202, first.text
    second = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true", "source_kind": "srt"},
        files={"file": ("sample.srt", srt, "application/x-subrip")},
    )
    assert second.status_code == 202, second.text
    assert first.json()["job_id"] == second.json()["job_id"]

    async def _jobs_used() -> int:
        async with client.app.state.session_factory() as session:
            svc = UsageService(session, client.app.state.settings)
            row = await svc._row(workspace_id)
            return row.jobs_used

    assert anyio.run(_jobs_used) == 1


def test_simulated_provider_outage_marks_actionable_failure() -> None:
    """Circuit open / exhausted retries → actionable taxonomy (job dead-letter)."""
    configure_circuit_breaker(failure_threshold=1, recovery_timeout_seconds=60.0)

    async def boom() -> None:
        raise ProviderTemporarilyUnavailable("simulated outage", provider="fake")

    async def run() -> None:
        with pytest.raises(ProviderTemporarilyUnavailable):
            await with_bounded_retry(boom, max_retries=0, provider="fake")
        with pytest.raises(CircuitOpenError) as exc:
            await with_bounded_retry(boom, max_retries=0, provider="fake")
        assert exc.value.code == "PROVIDER_CIRCUIT_OPEN"
        meta = classify_error(exc.value.code)
        assert meta["actionable"] is True

    anyio.run(run)
    decision = evaluate_retry(
        attempt=3,
        max_attempts=3,
        error_code="PROVIDER_CIRCUIT_OPEN",
        retryable=True,
    )
    assert decision.dead_letter is True
    assert classify_error(decision.error_code)["actionable"] is True


def test_job_lease_recovery(client: TestClient) -> None:
    body = _register(client, "lease-rec@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])

    async def _seed_and_recover() -> list[uuid.UUID]:
        async with client.app.state.session_factory() as session:
            job = IngestionJob(
                workspace_id=workspace_id,
                job_type="transcript_ingest",
                status="running",
                stage="persisting",
                attempt=1,
                idempotency_key=f"lease-{uuid.uuid4()}",
                percent=45,
                lease_until=datetime.now(UTC) - timedelta(minutes=5),
            )
            session.add(job)
            await session.flush()
            recovered = await recover_expired_leases(session)
            await session.commit()
            return recovered

    recovered = anyio.run(_seed_and_recover)
    assert len(recovered) == 1

    async def _status() -> str:
        async with client.app.state.session_factory() as session:
            row = await session.get(IngestionJob, recovered[0])
            assert row is not None
            assert row.last_error_code == "JOB_LEASE_EXPIRED"
            return row.status

    assert anyio.run(_status) == "queued"


def test_usage_limit_row_created(client: TestClient) -> None:
    body = _register(client, "usage-row@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    client.get("/api/v1/usage")

    async def _check() -> UsageLimit | None:
        async with client.app.state.session_factory() as session:
            result = await session.execute(
                select(UsageLimit).where(UsageLimit.workspace_id == workspace_id)
            )
            return result.scalar_one_or_none()

    row = anyio.run(_check)
    assert row is not None
    assert row.period == current_period()
    assert isinstance(row.spend_cap_usd, Decimal)
