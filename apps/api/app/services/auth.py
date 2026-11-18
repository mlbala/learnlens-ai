"""Authentication and session lifecycle service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    issue_access_token,
    normalize_email,
    refresh_expiry,
    verify_password,
)
from app.core.settings import Settings
from app.db.models import Session, User, Workspace
from app.db.repositories import SessionRepository, UserRepository, WorkspaceRepository

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def _as_utc(value: datetime) -> datetime:
    """Normalize DB datetimes (SQLite may return naive UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    csrf_token: str
    session: Session
    user: User
    workspace: Workspace


@dataclass(frozen=True)
class AuthContext:
    user: User
    workspace: Workspace
    session: Session


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._users = UserRepository(db)
        self._workspaces = WorkspaceRepository(db)
        self._sessions = SessionRepository(db)

    def validate_password_policy(self, password: str) -> str | None:
        if len(password) < MIN_PASSWORD_LENGTH:
            return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        if len(password) > MAX_PASSWORD_LENGTH:
            return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
        return None

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens | str:
        """Returns tokens on success, or an error code string."""
        policy_error = self.validate_password_policy(password)
        if policy_error:
            return "WEAK_PASSWORD"
        normalized = normalize_email(email)
        if not normalized or "@" not in normalized:
            return "INVALID_EMAIL"
        existing = await self._users.get_by_email(normalized)
        if existing is not None:
            return "EMAIL_TAKEN"
        user = await self._users.create(
            email=normalized,
            password_hash=hash_password(password),
            display_name=display_name.strip() if display_name else None,
        )
        workspace_name = (display_name or normalized.split("@", 1)[0] or "Workspace").strip()
        workspace = await self._workspaces.create_personal(
            owner_user_id=user.id,
            name=f"{workspace_name}'s workspace",
        )
        return await self._issue_session(user=user, workspace=workspace, user_agent=user_agent)

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
    ) -> AuthTokens | None:
        """Returns None for any credential failure (no email enumeration)."""
        normalized = normalize_email(email)
        user = await self._users.get_by_email(normalized)
        if user is None or user.status != "active":
            # Constant-ish work: hash a dummy to reduce timing oracle.
            hash_password("invalid-password-dummy")
            return None
        if not verify_password(user.password_hash, password):
            return None
        membership_workspace = await self._default_workspace(user.id)
        if membership_workspace is None:
            return None
        return await self._issue_session(
            user=user,
            workspace=membership_workspace,
            user_agent=user_agent,
        )

    async def refresh(
        self,
        *,
        refresh_token: str,
        user_agent: str | None = None,
    ) -> AuthTokens | None:
        row = await self._sessions.get_by_refresh_hash(hash_token(refresh_token))
        if row is None:
            return None
        now = datetime.now(UTC)
        if row.revoked_at is not None or _as_utc(row.expires_at) <= now:
            return None
        user = await self._users.get_by_id(row.user_id)
        workspace = await self._workspaces.get_by_id(row.workspace_id)
        if user is None or workspace is None or user.status != "active":
            await self._sessions.revoke(row)
            return None
        # Rotate: revoke old, issue new linked session.
        await self._sessions.revoke(row)
        return await self._issue_session(
            user=user,
            workspace=workspace,
            user_agent=user_agent,
            rotated_from_id=row.id,
        )

    async def logout(self, *, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        row = await self._sessions.get_by_refresh_hash(hash_token(refresh_token))
        if row is not None and row.revoked_at is None:
            await self._sessions.revoke(row)

    async def resolve_access(self, access_token: str) -> AuthContext | None:
        from app.core.security import decode_access_token

        payload = decode_access_token(self._settings, access_token)
        if payload is None:
            return None
        try:
            session_id = uuid.UUID(str(payload["sid"]))
            user_id = uuid.UUID(str(payload["uid"]))
            workspace_id = uuid.UUID(str(payload["wid"]))
        except (KeyError, ValueError, TypeError):
            return None
        row = await self._sessions.get_by_id(session_id)
        if row is None or row.revoked_at is not None:
            return None
        if row.user_id != user_id or row.workspace_id != workspace_id:
            return None
        if _as_utc(row.expires_at) <= datetime.now(UTC):
            return None
        user = await self._users.get_by_id(user_id)
        workspace = await self._workspaces.get_by_id(workspace_id)
        if user is None or workspace is None or user.status != "active":
            return None
        await self._sessions.touch(row)
        return AuthContext(user=user, workspace=workspace, session=row)

    async def verify_csrf(self, *, session: Session, csrf_header: str | None) -> bool:
        if not csrf_header:
            return False
        return hash_token(csrf_header) == session.csrf_token_hash

    async def _default_workspace(self, user_id: uuid.UUID) -> Workspace | None:
        from sqlalchemy import select

        from app.db.models import WorkspaceMembership

        result = await self._db.execute(
            select(Workspace)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(WorkspaceMembership.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _issue_session(
        self,
        *,
        user: User,
        workspace: Workspace,
        user_agent: str | None,
        rotated_from_id: uuid.UUID | None = None,
    ) -> AuthTokens:
        refresh_token = generate_token()
        csrf_token = generate_token(24)
        row = await self._sessions.create(
            user_id=user.id,
            workspace_id=workspace.id,
            refresh_token_hash=hash_token(refresh_token),
            csrf_token_hash=hash_token(csrf_token),
            expires_at=refresh_expiry(self._settings),
            user_agent=user_agent,
            rotated_from_id=rotated_from_id,
            device_info={"fixture": False},
        )
        access_token = issue_access_token(
            self._settings,
            user_id=str(user.id),
            session_id=str(row.id),
            workspace_id=str(workspace.id),
        )
        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            session=row,
            user=user,
            workspace=workspace,
        )
