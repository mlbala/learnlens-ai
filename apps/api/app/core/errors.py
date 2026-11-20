"""Public API error helpers — never include secrets or stack traces."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.policies.privacy_policy import PrivacyPolicy


def error_body(
    *,
    code: str,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": PrivacyPolicy.safe_error_message(message),
            "request_id": request_id,
            "details": PrivacyPolicy.redact_mapping(details or {}),
        }
    }


def raise_api_error(
    status_code: int,
    *,
    code: str,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail=error_body(code=code, message=message, request_id=request_id, details=details),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
        if request_id and not body["error"].get("request_id"):
            body["error"]["request_id"] = request_id
    else:
        body = error_body(
            code="HTTP_ERROR",
            message=str(detail),
            request_id=request_id,
        )
    return JSONResponse(status_code=exc.status_code, content=body)


def unauthorized(request_id: str | None = None) -> NoReturn:
    raise_api_error(
        status.HTTP_401_UNAUTHORIZED,
        code="UNAUTHENTICATED",
        message="Authentication required.",
        request_id=request_id,
    )


def forbidden(request_id: str | None = None) -> NoReturn:
    raise_api_error(
        status.HTTP_403_FORBIDDEN,
        code="FORBIDDEN",
        message="You do not have access to this resource.",
        request_id=request_id,
    )


def not_found(request_id: str | None = None) -> NoReturn:
    raise_api_error(
        status.HTTP_404_NOT_FOUND,
        code="NOT_FOUND",
        message="Resource not found.",
        request_id=request_id,
    )
