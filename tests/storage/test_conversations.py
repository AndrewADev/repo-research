"""Tests for conversation storage."""

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


def test_create_conversation(temp_db):
    """Test creating a new conversation."""
    store = ConversationStore(temp_db)
    thread_id = "test-thread-1"

    conv_id = store.create_conversation(thread_id, "test-command", "Test conversation")

    assert conv_id > 0
    assert store.conversation_exists(thread_id)


def test_add_message(temp_db):
    """Test adding messages to a conversation."""
    store = ConversationStore(temp_db)
    thread_id = "test-thread-2"

    store.create_conversation(thread_id, "test-command", "Test conversation")
    store.add_message(thread_id, "user", "Hello, world!")
    store.add_message(thread_id, "assistant", "Hi there!")

    conversation = store.get_conversation(thread_id)
    assert len(conversation["messages"]) == 2
    assert conversation["messages"][0]["role"] == "user"
    assert conversation["messages"][0]["content"] == "Hello, world!"
    assert conversation["messages"][1]["role"] == "assistant"
    assert conversation["messages"][1]["content"] == "Hi there!"


def test_list_conversations(temp_db):
    """Test listing conversations."""
    store = ConversationStore(temp_db)

    # Create multiple conversations
    store.create_conversation("thread-1", "analyze", "Analysis 1")
    store.create_conversation("thread-2", "topics", "Topics search")
    store.create_conversation("thread-3", "diagnostics", "Diagnostics run")

    conversations = store.list_conversations()
    assert len(conversations) == 3
    assert all("thread_id" in conv for conv in conversations)
    assert all("command" in conv for conv in conversations)


def test_get_conversation(temp_db):
    """Test retrieving a specific conversation."""
    store = ConversationStore(temp_db)
    thread_id = "test-thread-3"

    store.create_conversation(thread_id, "test-command", "Test conversation")
    store.add_message(thread_id, "user", "Test message")

    conversation = store.get_conversation(thread_id)
    assert conversation is not None
    assert conversation["thread_id"] == thread_id
    assert conversation["command"] == "test-command"
    assert len(conversation["messages"]) == 1


def test_get_nonexistent_conversation(temp_db):
    """Test retrieving a conversation that doesn't exist."""
    store = ConversationStore(temp_db)
    conversation = store.get_conversation("nonexistent-thread")
    assert conversation is None


def test_update_summary(temp_db):
    """Test updating conversation summary."""
    store = ConversationStore(temp_db)
    thread_id = "test-thread-4"

    store.create_conversation(thread_id, "test-command", "Original summary")
    store.update_summary(thread_id, "Updated summary")

    conversation = store.get_conversation(thread_id)
    assert conversation is not None, (
        f"Expected to find conversation with thread_id '{thread_id}'"
    )
    assert conversation["summary"] == "Updated summary"


def test_delete_conversation(temp_db):
    """Test deleting a conversation."""
    store = ConversationStore(temp_db)
    thread_id = "test-thread-5"

    store.create_conversation(thread_id, "test-command", "Test conversation")
    store.add_message(thread_id, "user", "Test message")

    assert store.conversation_exists(thread_id)
    result = store.delete_conversation(thread_id)
    assert result is True
    assert not store.conversation_exists(thread_id)


def test_delete_nonexistent_conversation(temp_db):
    """Test deleting a conversation that doesn't exist."""
    store = ConversationStore(temp_db)
    result = store.delete_conversation("nonexistent-thread")
    assert result is False


def test_message_with_metadata(temp_db):
    """Test storing messages with metadata."""
    store = ConversationStore(temp_db)
    thread_id = "test-thread-6"

    store.create_conversation(thread_id, "test-command", "Test conversation")

    metadata = {"tool_calls": ["search_repos"], "tokens": 150}
    store.add_message(thread_id, "assistant", "Response", metadata=metadata)

    conversation = store.get_conversation(thread_id)
    assert conversation is not None, (
        f"Expected to find conversation with thread_id '{thread_id}'"
    )
    message = conversation["messages"][0]
    assert message["metadata"] == metadata


def test_model_name_persistence(temp_db):
    """Test storing and retrieving model_name."""
    store = ConversationStore(temp_db)
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


def test_model_name_in_list(temp_db):
    """Test model_name appears in conversation list."""
    store = ConversationStore(temp_db)

    store.create_conversation("thread-1", "analyze", "Analysis", model_name="qwen3:8b")
    store.create_conversation(
        "thread-2", "topics", "Topics", model_name="claude-3-opus-20240229"
    )

    conversations = store.list_conversations()
    # Reverse-chronological sort by default
    assert conversations[0]["model_name"] == "claude-3-opus-20240229"
    assert conversations[1]["model_name"] == "qwen3:8b"
