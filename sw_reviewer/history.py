"""In-memory per-thread conversation history store."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic_ai.messages import ModelMessage


ThreadKey = tuple[str, str, str]  # (team_id, channel_id, thread_ts)


class ConversationStore:
    """Thread-safe in-memory store for pydantic-ai message histories.

    Keyed by (team_id, channel_id, thread_ts) for Slack threads.
    """

    def __init__(self) -> None:
        self._store: dict[ThreadKey, list[ModelMessage]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: ThreadKey) -> list[ModelMessage]:
        async with self._lock:
            return list(self._store.get(key, []))

    async def save(self, key: ThreadKey, messages: list[ModelMessage]) -> None:
        async with self._lock:
            self._store[key] = list(messages)

    async def delete(self, key: ThreadKey) -> None:
        async with self._lock:
            self._store.pop(key, None)
