"""Shared test fixtures and utilities."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest

# ----------------------------------------------------------------------------
# Async-generator helpers for mocking `graph.astream_events`.
#
# `async def` without any `yield` produces a coroutine, not an async generator,
# so the unreachable `yield` below is load-bearing — it makes Python compile
# the function as an async generator that simply returns immediately.
# ----------------------------------------------------------------------------


async def empty_async_iter(*_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
    """Async generator that yields nothing. Drop-in for `graph.astream_events`
    in mock-based tests where you just need the call to complete cleanly."""
    return
    yield  # unreachable; marks this as an async generator


def raising_async_iter(exc: Exception) -> Callable[..., AsyncIterator[Any]]:
    """Return an async-generator function that raises `exc` on first iteration.

    Used to simulate failures inside the graph stream, which `emit_agui_events`
    converts to a `RunErrorEvent` for the renderer to display.
    """

    async def _gen(*_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
        raise exc
        yield  # unreachable; marks this as an async generator

    return _gen


def recording_async_iter() -> tuple[
    Callable[..., AsyncIterator[Any]], list[dict[str, Any]]
]:
    """Return `(fn, calls)` where `fn` is an empty async-generator mock and
    `calls` records every invocation's args/kwargs.

    Lets tests assert on how `graph.astream_events` was called without having
    to wire up a full mock with `side_effect` plumbing.
    """
    calls: list[dict[str, Any]] = []

    async def _gen(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        calls.append({"args": args, "kwargs": kwargs})
        return
        yield  # unreachable; marks this as an async generator

    return _gen, calls


class MockConversationStore:
    """In-memory mock of ConversationStore for testing."""

    def __init__(self, db_path: str | None = None):
        """Initialize mock store."""
        self.db_path = db_path
        self.conversations = {}  # thread_id -> conversation data
        self.messages = {}  # thread_id -> list of messages

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return False

    def close(self):
        """Close any resources (for compatibility)."""
        pass

    def create_conversation(
        self,
        thread_id: str,
        command: str,
        summary: str | None = None,
        model_name: str | None = None,
    ) -> int:
        """Create a new conversation metadata record."""
        now = datetime.now(UTC).isoformat()
        conv_id = len(self.conversations) + 1

        self.conversations[thread_id] = {
            "id": conv_id,
            "thread_id": thread_id,
            "command": command,
            "model_name": model_name,
            "summary": summary,
            "created_at": now,
            "updated_at": now,
        }
        self.messages[thread_id] = []
        return conv_id

    def get_conversation(self, thread_id: str) -> dict[str, Any] | None:
        """Get conversation with all messages."""
        if thread_id not in self.conversations:
            return None

        conversation = self.conversations[thread_id].copy()
        conversation["messages"] = self.messages[thread_id].copy()
        return conversation

    def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent conversations."""
        conversations = []
        for thread_id, conv in self.conversations.items():
            conv_copy = conv.copy()
            conv_copy["message_count"] = len(self.messages[thread_id])
            conversations.append(conv_copy)

        # Sort by updated_at DESC
        conversations.sort(key=lambda x: x["updated_at"], reverse=True)
        return conversations[:limit]

    def update_summary(self, thread_id: str, summary: str):
        """Update conversation summary."""
        if thread_id in self.conversations:
            now = datetime.now(UTC).isoformat()
            self.conversations[thread_id]["summary"] = summary
            self.conversations[thread_id]["updated_at"] = now

    def delete_conversation(self, thread_id: str) -> bool:
        """Delete a conversation and its messages."""
        if thread_id not in self.conversations:
            return False

        del self.conversations[thread_id]
        del self.messages[thread_id]
        return True

    def conversation_exists(self, thread_id: str) -> bool:
        """Check if a conversation exists."""
        return thread_id in self.conversations


@pytest.fixture
def mock_store():
    """Create a mock conversation store for testing."""
    with MockConversationStore() as store:
        yield store
