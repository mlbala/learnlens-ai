"""FastAPI dependencies — DB session, auth context, CSRF checks."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import raise_api_error, unauthorized
from app.core.settings import Settings, get_settings
from app.services.auth import AuthContext, AuthService


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise_api_error(
            503,
            code="DATABASE_UNAVAILABLE",
            message="Database is not configured.",
            request_id=getattr(request.state, "request_id", None),
        )
    return factory


async def get_db(
    request: Request,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_auth_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(db, settings)


async def get_current_auth(
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthContext:
    token = request.cookies.get(settings.access_cookie_name)
    request_id = getattr(request.state, "request_id", None)
    if not token:
        unauthorized(request_id)
    ctx = await auth.resolve_access(token)
    if ctx is None:
        unauthorized(request_id)
    return ctx  # type: ignore[return-value]


async def require_csrf(
    request: Request,
    ctx: Annotated[AuthContext, Depends(get_current_auth)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthContext:
    """Enforce double-submit CSRF on cookie-authenticated mutations."""
    request_id = getattr(request.state, "request_id", None)
    header = request.headers.get("X-CSRF-Token")
    if not await auth.verify_csrf(session=ctx.session, csrf_header=header):
        raise_api_error(
            403,
            code="CSRF_FAILED",
            message="CSRF validation failed.",
            request_id=request_id,
        )
    return ctx


async def get_optional_auth(
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthContext | None:
    token = request.cookies.get(settings.access_cookie_name)
    if not token:
        return None
    return await auth.resolve_access(token)


# Re-export for route typing clarity
CurrentAuth = Annotated[AuthContext, Depends(get_current_auth)]
CsrfAuth = Annotated[AuthContext, Depends(require_csrf)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
