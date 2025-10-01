"""Tests for chat command and interactive session functionality."""

import tempfile
import uuid
from pathlib import Path

import pytest
import typer

from github_agent.main import chat, resume, run_interactive_session
from storage.conversations import ConversationStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path


@pytest.fixture
def mock_graph(mocker):
    """Create a mock LangGraph instance."""
    graph = mocker.MagicMock()
    # Mock stream to return a simple response
    mock_message = mocker.MagicMock()
    mock_message.content = "Test response"
    graph.stream.return_value = [{"messages": [mock_message]}]
    return graph


class TestRunInteractiveSession:
    """Tests for run_interactive_session helper function."""

    def test_handles_user_input_and_stores_messages(self, temp_db, mock_graph, mocker):
        """Test that user input and assistant responses are processed and stored."""
        store = ConversationStore(temp_db)
        thread_id = str(uuid.uuid4())
        store.create_conversation(thread_id, "chat", "Test session")

        # Mock input to provide one message then exit
        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = ["Hello", "exit"]

        # Mock is_ai_message to return True for our mock messages
        mocker.patch("github_agent.main.is_ai_message", return_value=True)

        run_interactive_session(mock_graph, thread_id, store)

        # Verify both user and assistant messages were stored
        conversation = store.get_conversation(thread_id)
        assert conversation is not None, "Expected conversation to exist"
        assert len(conversation["messages"]) == 2  # User message + assistant response
        assert conversation["messages"][0]["role"] == "user"
        assert conversation["messages"][0]["content"] == "Hello"
        assert conversation["messages"][1]["role"] == "assistant"
        assert conversation["messages"][1]["content"] == "Test response"

    @pytest.mark.parametrize("exit_command", ["exit", "quit"])
    def test_handles_exit_commands(self, temp_db, mock_graph, mocker, exit_command):
        """Test that 'exit' and 'quit' commands terminate session."""
        store = ConversationStore(temp_db)
        thread_id = str(uuid.uuid4())
        store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = [exit_command]

        run_interactive_session(mock_graph, thread_id, store)

        # No messages should be stored when exiting immediately
        conversation = store.get_conversation(thread_id)
        assert conversation is not None, "Expected conversation to exist"
        assert len(conversation["messages"]) == 0

    @pytest.mark.parametrize(
        "inputs", [["", "exit"], ["  ", "exit"], ["", "  ", "exit"]]
    )
    def test_skips_empty_input(self, temp_db, mock_graph, mocker, inputs):
        """Test that empty and whitespace-only input is ignored."""
        store = ConversationStore(temp_db)
        thread_id = str(uuid.uuid4())
        store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = inputs

        run_interactive_session(mock_graph, thread_id, store)

        # No messages should be stored from empty inputs
        conversation = store.get_conversation(thread_id)
        assert conversation is not None, "Expected conversation to exist"
        assert len(conversation["messages"]) == 0

    def test_handles_keyboard_interrupt(self, temp_db, mock_graph, mocker):
        """Test that Ctrl+C (KeyboardInterrupt) exits gracefully."""
        store = ConversationStore(temp_db)
        thread_id = str(uuid.uuid4())
        store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = KeyboardInterrupt()

        # Should not raise exception
        run_interactive_session(mock_graph, thread_id, store)

    def test_handles_eof_error(self, temp_db, mock_graph, mocker):
        """Test that EOF (Ctrl+D) exits gracefully."""
        store = ConversationStore(temp_db)
        thread_id = str(uuid.uuid4())
        store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = EOFError()

        # Should not raise exception
        run_interactive_session(mock_graph, thread_id, store)


class TestChatCommand:
    """Tests for the chat command."""

    def test_creates_new_conversation(self, temp_db, mocker):
        """Test that chat command creates a new conversation."""
        # Mock dependencies
        mock_run_session = mocker.patch("github_agent.main.run_interactive_session")
        mock_create_graph = mocker.patch("github_agent.main.create_configured_graph")

        # Mock the conversation store to use our temp db
        mocker.patch(
            "github_agent.main.ConversationStore",
            return_value=ConversationStore(temp_db),
        )

        # Mock get_resolved_model_name
        mocker.patch(
            "github_agent.main.get_resolved_model_name", return_value="qwen3:8b"
        )

        # Mock UUID generation for predictability
        test_uuid = "test-uuid-1234"
        mocker.patch("github_agent.main.uuid.uuid4", return_value=test_uuid)

        mock_graph = mocker.MagicMock()
        mock_create_graph.return_value = mock_graph

        # Execute chat command
        chat(model_name=None)

        # Verify conversation was created
        store = ConversationStore(temp_db)
        conversation = store.get_conversation(test_uuid)
        assert conversation is not None, "Expected conversation to exist"
        assert conversation["thread_id"] == test_uuid
        assert conversation["command"] == "chat"
        assert conversation["summary"] == "Interactive chat session"
        assert conversation["model_name"] == "qwen3:8b"

        # Verify interactive session was started
        mock_run_session.assert_called_once_with(mock_graph, test_uuid, mocker.ANY)

    def test_uses_custom_model_name(self, temp_db, mocker):
        """Test that chat command respects custom model_name."""
        # Mock dependencies
        mocker.patch("github_agent.main.run_interactive_session")
        mock_create_graph = mocker.patch("github_agent.main.create_configured_graph")

        mocker.patch(
            "github_agent.main.ConversationStore",
            return_value=ConversationStore(temp_db),
        )
        mocker.patch(
            "github_agent.main.get_resolved_model_name",
            return_value="claude-3-opus-20240229",
        )

        test_uuid = "test-uuid-5678"
        mocker.patch("github_agent.main.uuid.uuid4", return_value=test_uuid)

        mock_graph = mocker.MagicMock()
        mock_create_graph.return_value = mock_graph

        # Execute with custom model
        chat(model_name="claude-3-opus-20240229")

        # Verify model_name was stored
        store = ConversationStore(temp_db)
        conversation = store.get_conversation(test_uuid)
        assert conversation is not None, "Expected conversation to exist"
        assert conversation["model_name"] == "claude-3-opus-20240229"

        # Verify graph was created with custom model
        mock_create_graph.assert_called_once_with("claude-3-opus-20240229")


class TestResumeCommand:
    """Tests for the resume command (after refactoring)."""

    def test_resumes_existing_conversation(self, temp_db, mocker):
        """Test that resume command works with existing conversation."""
        # Mock dependencies
        mock_run_session = mocker.patch("github_agent.main.run_interactive_session")
        mock_create_graph = mocker.patch("github_agent.main.create_configured_graph")

        store = ConversationStore(temp_db)
        thread_id = str(uuid.uuid4())
        store.create_conversation(
            thread_id, "chat", "Previous session", model_name="qwen3:8b"
        )
        store.add_message(thread_id, "user", "Previous message")

        mocker.patch(
            "github_agent.main.ConversationStore",
            return_value=ConversationStore(temp_db),
        )

        mock_graph = mocker.MagicMock()
        mock_create_graph.return_value = mock_graph

        # Execute resume
        resume(thread_id=thread_id, model_name=None)

        # Verify interactive session was started
        mock_run_session.assert_called_once_with(mock_graph, thread_id, mocker.ANY)

    def test_fails_on_nonexistent_conversation(self, temp_db, mocker):
        """Test that resume fails gracefully for nonexistent conversation."""
        mocker.patch(
            "github_agent.main.ConversationStore",
            return_value=ConversationStore(temp_db),
        )

        # Execute resume with nonexistent thread and expect typer.Exit exception
        with pytest.raises(typer.Exit) as exc_info:
            resume(thread_id="nonexistent-thread", model_name=None)

        # Verify it exited with error code 1
        assert exc_info.value.exit_code == 1


class TestIntegration:
    """Integration tests for chat and resume workflow."""

    def test_chat_creates_resumable_conversation(self, temp_db, mocker):
        """Test that a chat session can be resumed later."""
        # Setup mocks
        mock_create_graph = mocker.patch("github_agent.main.create_configured_graph")

        mock_graph = mocker.MagicMock()
        mock_message = mocker.MagicMock()
        mock_message.content = "Test response"
        mock_graph.stream.return_value = [{"messages": [mock_message]}]
        mock_create_graph.return_value = mock_graph

        store = ConversationStore(temp_db)
        mocker.patch("github_agent.main.ConversationStore", return_value=store)
        mocker.patch(
            "github_agent.main.get_resolved_model_name", return_value="qwen3:8b"
        )
        mocker.patch("github_agent.main.is_ai_message", return_value=True)

        test_uuid = str(uuid.uuid4())
        mocker.patch("github_agent.main.uuid.uuid4", return_value=test_uuid)

        # Mock user input for chat session
        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = ["Hello from chat", "exit"]

        # Execute chat command
        chat(model_name=None)

        # Verify conversation was created and has messages
        conversation = store.get_conversation(test_uuid)
        assert conversation is not None
        assert len(conversation["messages"]) == 2

        # Now resume the conversation
        mock_input.side_effect = ["Hello from resume", "exit"]

        resume(thread_id=test_uuid, model_name=None)

        # Verify new messages were added
        conversation = store.get_conversation(test_uuid)
        assert conversation is not None, "Expected conversation to exist"
        assert len(conversation["messages"]) == 4  # 2 from chat + 2 from resume
        assert conversation["messages"][2]["content"] == "Hello from resume"
