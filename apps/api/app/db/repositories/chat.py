"""Chat thread / message / citation repositories — workspace-scoped."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatMessage, ChatThread, MessageCitation


class ChatThreadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        scope_kind: str,
        scope_id: uuid.UUID | None,
        created_by: uuid.UUID,
        title: str | None = None,
    ) -> ChatThread:
        row = ChatThread(
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            created_by=created_by,
            title=title,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_in_workspace(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ChatThread | None:
        result = await self._session.execute(
            select(ChatThread).where(
                ChatThread.id == thread_id,
                ChatThread.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_for_scope(
        self,
        *,
        workspace_id: uuid.UUID,
        scope_kind: str,
        scope_id: uuid.UUID,
    ) -> ChatThread | None:
        result = await self._session.execute(
            select(ChatThread)
            .where(
                ChatThread.workspace_id == workspace_id,
                ChatThread.scope_kind == scope_kind,
                ChatThread.scope_id == scope_id,
            )
            .order_by(ChatThread.created_at.asc(), ChatThread.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class ChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
        role: str,
        content: str,
        explanation_mode: str | None = None,
        provider_run_id: uuid.UUID | None = None,
        confidence_label: str | None = None,
        unsupported: bool = False,
        content_json: dict[str, Any] | None = None,
        external_search_enabled: bool | None = None,
    ) -> ChatMessage:
        row = ChatMessage(
            thread_id=thread_id,
            workspace_id=workspace_id,
            role=role,
            content=content,
            explanation_mode=explanation_mode,
            provider_run_id=provider_run_id,
            confidence_label=confidence_label,
            unsupported=unsupported,
            content_json=content_json,
            external_search_enabled=external_search_enabled,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_thread(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: int = 50,
        after_id: uuid.UUID | None = None,
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.thread_id == thread_id,
                ChatMessage.workspace_id == workspace_id,
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(limit)
        )
        if after_id is not None:
            anchor = await self._session.scalar(
                select(ChatMessage).where(
                    ChatMessage.id == after_id,
                    ChatMessage.thread_id == thread_id,
                    ChatMessage.workspace_id == workspace_id,
                )
            )
            if anchor is not None:
                stmt = (
                    select(ChatMessage)
                    .where(
                        ChatMessage.thread_id == thread_id,
                        ChatMessage.workspace_id == workspace_id,
                        ChatMessage.created_at >= anchor.created_at,
                        ChatMessage.id != after_id,
                    )
                    .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                    .limit(limit)
                )
                # Strict cursor: only rows after the anchor in (created_at, id) order.
                rows = list((await self._session.execute(stmt)).scalars().all())
                return [
                    r
                    for r in rows
                    if (r.created_at, r.id) > (anchor.created_at, anchor.id)
                ][:limit]
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(
        self,
        *,
        thread_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: int = 32,
    ) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.thread_id == thread_id,
                ChatMessage.workspace_id == workspace_id,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows


class MessageCitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(
        self,
        *,
        message_id: uuid.UUID,
        workspace_id: uuid.UUID,
        citations: list[dict[str, Any]],
    ) -> list[MessageCitation]:
        rows: list[MessageCitation] = []
        for item in citations:
            row = MessageCitation(
                message_id=message_id,
                workspace_id=workspace_id,
                segment_id=item["segment_id"],
                video_id=item["video_id"],
                citation_key=str(item["citation_key"])[:32],
                snippet=str(item.get("snippet") or "")[:2000],
                start_ms=item.get("start_ms"),
                end_ms=item.get("end_ms"),
                timing_verified=bool(item.get("timing_verified")),
                youtube_url=item.get("youtube_url"),
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    async def list_for_messages(
        self,
        *,
        message_ids: list[uuid.UUID],
        workspace_id: uuid.UUID,
    ) -> list[MessageCitation]:
        if not message_ids:
            return []
        result = await self._session.execute(
            select(MessageCitation)
            .where(
                MessageCitation.message_id.in_(message_ids),
                MessageCitation.workspace_id == workspace_id,
            )
            .order_by(MessageCitation.citation_key.asc())
        )
        return list(result.scalars().all())
