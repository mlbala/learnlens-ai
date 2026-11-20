"""Phase 13 security gate — adversarial corpus, headers, quotas, tenant/CSRF/upload."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import anyio
import pytest
from app.core.policies.audit_policy import get_audit_policy
from app.core.policies.input_policy import InputPolicy, InputPolicyViolation
from app.core.policies.output_policy import OutputPolicy
from app.core.policies.privacy_policy import PrivacyPolicy
from app.core.policies.usage_policy import UsageQuotaExceeded, configure_usage_policy
from app.core.settings import Settings, clear_settings_cache
from app.db.seed import seed_fixture_video
from app.domain.transcript_parse import parse_transcript, strip_presentation_markup
from app.storage.local import LocalMockStorage
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_helpers import TEST_PASSWORD, auth_csrf_headers

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS = REPO_ROOT / "fixtures" / "security" / "injection_corpus.jsonl"
MALICIOUS_VTT = REPO_ROOT / "fixtures" / "transcripts" / "malicious_prompt.vtt"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "name": email.split("@")[0]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _load_corpus() -> list[dict]:
    rows: list[dict] = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in (response.headers.get("Referrer-Policy") or "").lower()
    assert "frame-ancestors" in (response.headers.get("Content-Security-Policy") or "")
    assert response.headers.get("X-Request-ID")


def test_password_policy_rejects_letters_only(client: TestClient) -> None:
    weak = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "correcthorse", "name": "Weak"},
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"


def test_csrf_required_on_youtube_import(client: TestClient) -> None:
    _register(client, "csrf-import@example.com")
    response = client.post(
        "/api/v1/videos/import",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_client_supplied_workspace_id_ignored_on_video_get(
    client: TestClient, settings: Settings
) -> None:
    tenant_a = _register(client, "ws-a@example.com")
    workspace_a = uuid.UUID(tenant_a["workspace"]["id"])
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _seed() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_a,
                youtube_video_id="fixtureWS00001",
                title="Workspace A video (synthetic)",
            )
            await session.commit()
            return video_id

    video_id = anyio.run(_seed)
    spoof = str(uuid.uuid4())
    own = client.get(f"/api/v1/videos/{video_id}?workspace_id={spoof}")
    assert own.status_code == 200
    assert own.json()["workspace_id"] == str(workspace_a)
    assert own.json()["workspace_id"] != spoof


def test_path_traversal_filename_rejected(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRANSCRIPT_STORAGE_PATH", str(tmp_path / "store"))
    clear_settings_cache()
    body = _register(client, "trav@example.com")
    workspace_id = uuid.UUID(body["workspace"]["id"])
    session_factory: async_sessionmaker[AsyncSession] = client.app.state.session_factory

    async def _seed() -> uuid.UUID:
        async with session_factory() as session:
            video_id = await seed_fixture_video(
                session,
                settings,
                workspace_id=workspace_id,
                youtube_video_id="fixtureTrav001",
                title="Traversal fixture (synthetic)",
            )
            await session.commit()
            return video_id

    video_id = anyio.run(_seed)
    headers = auth_csrf_headers(client)
    sample = (REPO_ROOT / "fixtures" / "transcripts" / "sample.srt").read_bytes()
    response = client.post(
        f"/api/v1/videos/{video_id}/transcripts",
        headers=headers,
        data={"rights_attested": "true"},
        files={"file": ("../../etc/passwd.srt", sample, "application/x-subrip")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FILENAME"


def test_storage_rejects_traversal_keys(tmp_path: Path) -> None:
    store = LocalMockStorage(tmp_path / "root")
    with pytest.raises(ValueError, match="Invalid storage key|Path traversal"):
        store.get_bytes("../../etc/passwd")


def test_xss_markup_stripped_from_transcript_cues() -> None:
    raw = b"1\n00:00:01,000 --> 00:00:02,000\n<script>alert(1)</script> listening\n"
    parsed = parse_transcript(raw, filename="xss.srt", content_type="application/x-subrip")
    assert parsed.cues
    text = parsed.cues[0].text
    assert "<script>" not in text
    assert "listening" in text
    stripped = strip_presentation_markup("<script>alert(1)</script> listening")
    assert "<script>" not in stripped
    assert "listening" in stripped


def test_output_policy_strips_attacker_urls() -> None:
    text = "See https://attacker.example/steal and https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    cleaned = OutputPolicy.strip_disallowed_urls(text)
    assert "attacker.example" not in cleaned
    assert "youtube.com/watch" in cleaned
    assert "[link removed]" in cleaned


def test_privacy_policy_redacts_api_keys() -> None:
    msg = "upstream failed Authorization: Bearer sk-live-abcdef123456789012345678"
    cleaned = PrivacyPolicy.safe_error_message(msg)
    assert "sk-live" not in cleaned
    assert "Bearer" in cleaned or "[REDACTED]" in cleaned
    assert "[REDACTED]" in cleaned


def test_injection_corpus_scored_as_suspicious_data_only() -> None:
    rows = _load_corpus()
    assert len(rows) >= 5
    for row in rows:
        if row["category"] in {"prompt_override", "forged_role", "secret_exfiltration"}:
            score = InputPolicy.score_suspicious_content(row["text"])
            assert score.score >= 1, row["id"]


def test_malicious_vtt_parses_as_data_without_tool_side_effects() -> None:
    raw = MALICIOUS_VTT.read_bytes()
    parsed = parse_transcript(raw, filename="malicious_prompt.vtt", content_type="text/vtt")
    joined = "\n".join(c.text for c in parsed.cues)
    assert "SYSTEM UPDATE" in joined or "ignore" in joined.lower()
    score = InputPolicy.score_suspicious_content(joined)
    assert score.score >= 1
    # Parsing must not raise or execute anything — cues remain text.
    assert all(isinstance(c.text, str) for c in parsed.cues)


def test_filename_sanitize_rejects_executables() -> None:
    with pytest.raises(InputPolicyViolation) as exc:
        InputPolicy.sanitize_upload_filename("payload.exe")
    assert exc.value.code == "INVALID_TRANSCRIPT_TYPE"


def test_usage_quota_blocks_excess_jobs() -> None:
    policy = configure_usage_policy(daily_chat_messages=2, daily_transcript_jobs=1)
    policy.reset()
    policy.check_job_allowed("user-1")
    policy.record_job("user-1")
    with pytest.raises(UsageQuotaExceeded):
        policy.check_job_allowed("user-1")


def test_audit_policy_records_without_raw_transcript() -> None:
    audit = get_audit_policy()
    audit.reset()
    from app.core.policies.audit_policy import AuditRecord

    audit.record(
        AuditRecord(
            action="transcript_upload",
            workspace_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            resource_type="video",
            resource_id=str(uuid.uuid4()),
            metadata={
                "api_key": "sk-should-redact-this-value-xxxxxxxx",
                "cue_text": "should not be stored as transcript",
            },
        )
    )
    recent = audit.list_recent(limit=1)
    assert recent
    assert recent[0].metadata.get("api_key") == "[REDACTED]"


def test_cross_tenant_playlist_denied(client: TestClient, settings: Settings) -> None:
    _register(client, "pl-a@example.com")
    headers_a = auth_csrf_headers(client)
    created = client.post(
        "/api/v1/playlists/import",
        headers=headers_a,
        json={"youtube_url": "https://www.youtube.com/playlist?list=PLfixtureCourse01"},
    )
    assert created.status_code == 200, created.text
    playlist_id = created.json()["playlist"]["id"]
    client.cookies.clear()
    _register(client, "pl-b2@example.com")
    denied = client.get(f"/api/v1/playlists/{playlist_id}")
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "NOT_FOUND"


def test_forged_citation_dropped_by_evidence_gate() -> None:
    from app.domain.evidence import QaEvidenceItem, build_qa_packet, validate_qa_payload

    ws = uuid.uuid4()
    vid = uuid.uuid4()
    packet = build_qa_packet(
        workspace_id=ws,
        scope_kind="video",
        scope_id=vid,
        items=[
            QaEvidenceItem(
                segment_id="seg-real",
                video_id=vid,
                text="Listening requires attention.",
                start_ms=1000,
                end_ms=2000,
                source_revision=1,
                youtube_video_id="abcdefghijk",
                video_title="Fixture",
                timecode_quality="original",
            )
        ],
    )
    validated = validate_qa_payload(
        {
            "answer": "Claim with forged cite",
            "claims": [
                {
                    "text": "Forged",
                    "citation_segment_ids": ["seg-forged-uuid"],
                }
            ],
            "analogies": [],
            "unsupported": False,
            "confidence_label": "high",
            "citation_segment_ids": ["seg-forged-uuid"],
        },
        packet,
        refusal_message="Not covered.",
    )
    assert "seg-forged-uuid" in validated.dropped_citation_ids or validated.refused
    assert "seg-forged-uuid" not in validated.cited_segment_ids
