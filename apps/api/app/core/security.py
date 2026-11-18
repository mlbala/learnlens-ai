"""Password hashing, token generation, and cookie helpers (no secrets in logs)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.responses import Response

from app.core.settings import Settings

_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(raw: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_token(raw), hashed)


def _access_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="learnlens-access-v1")


def issue_access_token(
    settings: Settings,
    *,
    user_id: str,
    session_id: str,
    workspace_id: str,
) -> str:
    payload = {
        "uid": user_id,
        "sid": session_id,
        "wid": workspace_id,
        "typ": "access",
    }
    return _access_serializer(settings).dumps(payload)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any] | None:
    try:
        data = _access_serializer(settings).loads(token, max_age=settings.access_token_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or data.get("typ") != "access":
        return None
    return data


def cookie_secure(settings: Settings) -> bool:
    """Secure flag is required outside local development."""
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    return settings.environment.lower() not in {"development", "test", "local"}


def set_auth_cookies(
    response: Response,
    settings: Settings,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    secure = cookie_secure(settings)
    common = {
        "httponly": True,
        "secure": secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        settings.access_cookie_name,
        access_token,
        max_age=settings.access_token_ttl_seconds,
        **common,
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        **common,
    )
    # Double-submit CSRF: readable by JS, compared to X-CSRF-Token header.
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=False,
        secure=secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    secure = cookie_secure(settings)
    for name, httponly in (
        (settings.access_cookie_name, True),
        (settings.refresh_cookie_name, True),
        (settings.csrf_cookie_name, False),
    ):
        response.delete_cookie(
            name,
            path="/",
            secure=secure,
            httponly=httponly,
            samesite=settings.cookie_samesite,
        )


def refresh_expiry(settings: Settings) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_seconds)
