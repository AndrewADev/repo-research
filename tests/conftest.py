"""Shared test fixtures and utilities."""

from datetime import UTC, datetime
from typing import Any

import pytest


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
        """Create a new conversation."""
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

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a message to a conversation."""
        if thread_id not in self.conversations:
            raise ValueError(f"Conversation with thread_id {thread_id} not found")

        now = datetime.now(UTC).isoformat()
        self.messages[thread_id].append(
            {
                "role": role,
                "content": content,
                "metadata": metadata,
                "created_at": now,
            }
        )

        # Update conversation timestamp
        self.conversations[thread_id]["updated_at"] = now

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
