"""The evidence the retrieve step chose, kept briefly for the messages step.

The web route calls retrieve, writes the draft from that evidence, then calls
messages. Without this, messages searched and reranked again and could keep
different passages from the ones the draft was written from. The packet lives
only in this API process, never comes from the client, and is keyed by the
authenticated workspace, video, thread, question, and search setting. When it is
missing (a restart, another process, or more than TTL_SECONDS later), messages
builds the packet again as before.
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

TTL_SECONDS = 600.0
MAX_PACKETS = 256


@dataclass(frozen=True, slots=True)
class PacketKey:
    workspace_id: uuid.UUID
    video_id: uuid.UUID
    thread_id: uuid.UUID
    question: str
    external_search: bool


def packet_key(
    *,
    workspace_id: uuid.UUID,
    video_id: uuid.UUID,
    thread_id: uuid.UUID,
    question: str,
    external_search: bool,
) -> PacketKey:
    return PacketKey(
        workspace_id=workspace_id,
        video_id=video_id,
        thread_id=thread_id,
        question=" ".join(question.split()),
        external_search=bool(external_search),
    )


_PACKETS: OrderedDict[PacketKey, tuple[float, Any]] = OrderedDict()


def remember_packet(key: PacketKey, packet: Any, *, now: float | None = None) -> None:
    stamp = time.monotonic() if now is None else now
    _PACKETS[key] = (stamp + TTL_SECONDS, packet)
    _PACKETS.move_to_end(key)
    while len(_PACKETS) > MAX_PACKETS:
        _PACKETS.popitem(last=False)


def take_packet(key: PacketKey, *, now: float | None = None) -> Any | None:
    """The packet for this turn, once. None when missing or expired."""
    entry = _PACKETS.pop(key, None)
    if entry is None:
        return None
    expires, packet = entry
    stamp = time.monotonic() if now is None else now
    return packet if stamp <= expires else None


def clear_packets() -> None:
    _PACKETS.clear()
