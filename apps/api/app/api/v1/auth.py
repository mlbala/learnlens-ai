"""Auth endpoints: register / login / refresh / logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import DbSession, SettingsDep, get_auth_service
from app.api.v1.schemas import AuthOkResponse, LoginRequest, RegisterRequest, UserOut, WorkspaceOut
from app.core.errors import raise_api_error
from app.core.rate_limit import auth_rate_limiter
from app.core.security import clear_auth_cookies, hash_token, set_auth_cookies
from app.core.settings import Settings
from app.db.repositories import SessionRepository
from app.services.auth import AuthService, AuthTokens

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{email.strip().lower()}"


def _apply_tokens(response: Response, settings: Settings, tokens: AuthTokens) -> AuthOkResponse:
    set_auth_cookies(
        response,
        settings,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=tokens.csrf_token,
    )
    return AuthOkResponse(
        user=UserOut.model_validate(tokens.user),
        workspace=WorkspaceOut.model_validate(tokens.workspace),
    )


@router.post("/register", response_model=AuthOkResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthOkResponse:
    request_id = getattr(request.state, "request_id", None)
    if not auth_rate_limiter.allow(_client_key(request, str(body.email))):
        raise_api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message="Too many authentication attempts. Try again later.",
            request_id=request_id,
        )
    result = await auth.register(
        email=str(body.email),
        password=body.password,
        display_name=body.name,
        user_agent=request.headers.get("user-agent"),
    )
    if isinstance(result, str):
        if result == "EMAIL_TAKEN":
            raise_api_error(
                status.HTTP_409_CONFLICT,
                code="EMAIL_TAKEN",
                message="Unable to create account with the provided email.",
                request_id=request_id,
            )
        if result == "WEAK_PASSWORD":
            raise_api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="WEAK_PASSWORD",
                message="Password does not meet policy requirements.",
                request_id=request_id,
            )
        raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_EMAIL",
            message="Email is invalid.",
            request_id=request_id,
        )
    return _apply_tokens(response, settings, result)


@router.post("/login", response_model=AuthOkResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthOkResponse:
    request_id = getattr(request.state, "request_id", None)
    if not auth_rate_limiter.allow(_client_key(request, str(body.email))):
        raise_api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message="Too many authentication attempts. Try again later.",
            request_id=request_id,
        )
    tokens = await auth.login(
        email=str(body.email),
        password=body.password,
        user_agent=request.headers.get("user-agent"),
    )
    if tokens is None:
        # Identical message whether email exists or not.
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
            request_id=request_id,
        )
    return _apply_tokens(response, settings, tokens)


@router.post("/refresh", response_model=AuthOkResponse)
async def refresh(
    request: Request,
    response: Response,
    settings: SettingsDep,
    db: DbSession,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthOkResponse:
    request_id = getattr(request.state, "request_id", None)
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            message="Authentication required.",
            request_id=request_id,
        )
    # CSRF required for refresh (state-changing cookie mutation).
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise_api_error(
            status.HTTP_403_FORBIDDEN,
            code="CSRF_FAILED",
            message="CSRF validation failed.",
            request_id=request_id,
        )
    sessions = SessionRepository(db)
    existing = await sessions.get_by_refresh_hash(hash_token(refresh_token))
    if existing is None or hash_token(csrf_header) != existing.csrf_token_hash:
        raise_api_error(
            status.HTTP_403_FORBIDDEN,
            code="CSRF_FAILED",
            message="CSRF validation failed.",
            request_id=request_id,
        )
    tokens = await auth.refresh(
        refresh_token=refresh_token,
        user_agent=request.headers.get("user-agent"),
    )
    if tokens is None:
        clear_auth_cookies(response, settings)
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            code="SESSION_EXPIRED",
            message="Session expired. Please sign in again.",
            request_id=request_id,
        )
    return _apply_tokens(response, settings, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    settings: SettingsDep,
    db: DbSession,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    request_id = getattr(request.state, "request_id", None)
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)

    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise_api_error(
            status.HTTP_403_FORBIDDEN,
            code="CSRF_FAILED",
            message="CSRF validation failed.",
            request_id=request_id,
        )

    if refresh_token:
        sessions = SessionRepository(db)
        row = await sessions.get_by_refresh_hash(hash_token(refresh_token))
        if row is not None and hash_token(csrf_header) != row.csrf_token_hash:
            raise_api_error(
                status.HTTP_403_FORBIDDEN,
                code="CSRF_FAILED",
                message="CSRF validation failed.",
                request_id=request_id,
            )
        await auth.logout(refresh_token=refresh_token)

    clear_auth_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
