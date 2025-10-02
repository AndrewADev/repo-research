"""Tests for conversation metadata storage.

Note: These tests focus on conversation metadata only.
Message persistence is handled by LangGraph's SqliteSaver and tested separately.
"""

import tempfile
from pathlib import Path

import pytest

from storage.conversations import ConversationStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create a conversation store for testing."""
    store = ConversationStore(temp_db)
    yield store
    store.close()


def test_create_conversation(store):
    """Test creating a new conversation."""
    thread_id = "test-thread-1"

    conv_id = store.create_conversation(thread_id, "test-command", "Test conversation")

    assert conv_id > 0
    assert store.conversation_exists(thread_id)


def test_list_conversations(store):
    """Test listing conversations."""
    # Create multiple conversations
    store.create_conversation("thread-1", "analyze", "Analysis 1")
    store.create_conversation("thread-2", "topics", "Topics search")
    store.create_conversation("thread-3", "diagnostics", "Diagnostics run")

    conversations = store.list_conversations()
    assert len(conversations) == 3
    assert all("thread_id" in conv for conv in conversations)
    assert all("command" in conv for conv in conversations)


def test_get_conversation(store):
    """Test retrieving conversation metadata."""
    thread_id = "test-thread-3"

    store.create_conversation(thread_id, "test-command", "Test conversation")

    conversation = store.get_conversation(thread_id)
    assert conversation is not None
    assert conversation["thread_id"] == thread_id
    assert conversation["command"] == "test-command"
    # Messages come from checkpoints (empty in this test without LangGraph execution)
    assert "messages" in conversation


def test_get_nonexistent_conversation(store):
    """Test retrieving a conversation that doesn't exist."""
    conversation = store.get_conversation("nonexistent-thread")
    assert conversation is None


def test_update_summary(store):
    """Test updating conversation summary."""
    thread_id = "test-thread-4"

    store.create_conversation(thread_id, "test-command", "Original summary")
    store.update_summary(thread_id, "Updated summary")

    conversation = store.get_conversation(thread_id)
    assert conversation is not None, (
        f"Expected to find conversation with thread_id '{thread_id}'"
    )
    assert conversation["summary"] == "Updated summary"


def test_delete_conversation(store):
    """Test deleting a conversation's metadata."""
    thread_id = "test-thread-5"

    store.create_conversation(thread_id, "test-command", "Test conversation")

    assert store.conversation_exists(thread_id)
    result = store.delete_conversation(thread_id)
    assert result is True
    assert not store.conversation_exists(thread_id)


def test_delete_nonexistent_conversation(store):
    """Test deleting a conversation that doesn't exist."""
    result = store.delete_conversation("nonexistent-thread")
    assert result is False


def test_model_name_persistence(store):
    """Test storing and retrieving model_name."""
    thread_id = "test-thread-7"
    model_name = "qwen3:8b"

    store.create_conversation(
        thread_id, "test-command", "Test conversation", model_name=model_name
    )

    conversation = store.get_conversation(thread_id)
    assert conversation is not None, (
        f"Expected to find conversation with thread_id '{thread_id}'"
    )
    assert conversation["model_name"] == model_name


def test_model_name_in_list(store):
    """Test model_name appears in conversation list."""
    store.create_conversation("thread-1", "analyze", "Analysis", model_name="qwen3:8b")
    store.create_conversation(
        "thread-2", "topics", "Topics", model_name="claude-3-opus-20240229"
    )

    conversations = store.list_conversations()
    # Reverse-chronological sort by default
    assert conversations[0]["model_name"] == "claude-3-opus-20240229"
    assert conversations[1]["model_name"] == "qwen3:8b"


def test_get_most_recent_conversation_with_conversations(store):
    """Test getting the most recent conversation when conversations exist."""
    store.create_conversation("thread-1", "analyze", "First")
    store.create_conversation("thread-2", "topics", "Second")
    store.create_conversation("thread-3", "diagnostics", "Third")

    recent = store.get_most_recent_conversation()
    assert recent is not None
    assert recent["thread_id"] == "thread-3"
    assert recent["command"] == "diagnostics"


def test_get_most_recent_conversation_empty_store(store):
    """Test getting the most recent conversation when no conversations exist."""
    recent = store.get_most_recent_conversation()
    assert recent is None


def test_get_most_recent_conversation_returns_latest_updated(store):
    """Test that get_most_recent_conversation returns the most recently updated."""
    store.create_conversation("thread-1", "analyze", "First")
    store.create_conversation("thread-2", "topics", "Second")

    # Update the first conversation to make it most recent
    store.update_summary("thread-1", "Updated first conversation")

    recent = store.get_most_recent_conversation()
    assert recent is not None
    assert recent["thread_id"] == "thread-1"
    assert recent["summary"] == "Updated first conversation"
