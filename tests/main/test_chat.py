"""Tests for chat command and interactive session functionality."""

import uuid

import pytest

from github_agent.main import chat, resume_conversation, run_interactive_session
from tests.conftest import empty_async_iter, recording_async_iter


@pytest.fixture
def mock_graph(mocker):
    """Create a mock LangGraph instance whose astream_events yields nothing.

    The mock's `astream_events.calls` list records every invocation, so tests
    can assert on the state/config the runner passed in.
    """
    graph = mocker.MagicMock()
    astream, calls = recording_async_iter()
    graph.astream_events = astream
    graph.astream_events.calls = calls  # type: ignore[attr-defined]
    return graph


class TestRunInteractiveSession:
    """Tests for run_interactive_session helper function."""

    def test_handles_user_input_and_stores_messages(
        self, mock_store, mock_graph, mocker
    ):
        """Test that user input and assistant responses are processed.

        Note: Messages are now persisted by LangGraph's SqliteSaver automatically,
        so we just verify that the graph was invoked correctly.
        """
        thread_id = str(uuid.uuid4())
        mock_store.create_conversation(thread_id, "chat", "Test session")

        # Mock input to provide one message then exit
        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = ["Hello", "exit"]

        run_interactive_session(mock_graph, thread_id)

        # Verify graph.astream_events was called once with the user input.
        calls = mock_graph.astream_events.calls  # type: ignore[attr-defined]
        assert len(calls) == 1
        # State is the first positional arg; config follows positionally or
        # is passed as a kwarg.
        state = calls[0]["args"][0]
        assert state["messages"][0] == ("user", "Hello")
        config = calls[0]["kwargs"].get("config") or (
            calls[0]["args"][1] if len(calls[0]["args"]) > 1 else None
        )
        assert config is not None
        assert config["configurable"]["thread_id"] == thread_id

    @pytest.mark.parametrize("exit_command", ["exit", "quit"])
    def test_handles_exit_commands(self, mock_store, mock_graph, mocker, exit_command):
        """Test that 'exit' and 'quit' commands terminate session."""
        thread_id = str(uuid.uuid4())
        mock_store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = [exit_command]

        run_interactive_session(mock_graph, thread_id)

        # No messages should be stored when exiting immediately
        conversation = mock_store.get_conversation(thread_id)
        assert conversation is not None, "Expected conversation to exist"
        assert len(conversation["messages"]) == 0

    @pytest.mark.parametrize(
        "inputs", [["", "exit"], ["  ", "exit"], ["", "  ", "exit"]]
    )
    def test_skips_empty_input(self, mock_store, mock_graph, mocker, inputs):
        """Test that empty and whitespace-only input is ignored."""
        thread_id = str(uuid.uuid4())
        mock_store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = inputs

        run_interactive_session(mock_graph, thread_id)

        # No messages should be stored from empty inputs
        conversation = mock_store.get_conversation(thread_id)
        assert conversation is not None, "Expected conversation to exist"
        assert len(conversation["messages"]) == 0

    def test_handles_keyboard_interrupt(self, mock_store, mock_graph, mocker):
        """Test that Ctrl+C (KeyboardInterrupt) exits gracefully."""
        thread_id = str(uuid.uuid4())
        mock_store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = KeyboardInterrupt()

        # Should not raise exception
        run_interactive_session(mock_graph, thread_id)

    def test_handles_eof_error(self, mock_store, mock_graph, mocker):
        """Test that EOF (Ctrl+D) exits gracefully."""
        thread_id = str(uuid.uuid4())
        mock_store.create_conversation(thread_id, "chat", "Test session")

        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = EOFError()

        # Should not raise exception
        run_interactive_session(mock_graph, thread_id)


class TestChatCommand:
    """Tests for the chat command."""

    def test_creates_new_conversation(self, mock_store, mocker):
        """Test that chat command creates a new conversation."""
        # Mock dependencies
        mock_run_session = mocker.patch(
            "github_agent.commands.chat.run_interactive_session"
        )
        mock_create_graph = mocker.patch(
            "github_agent.commands.chat.create_configured_agent"
        )

        # Mock the conversation store to use our test store
        mocker.patch(
            "github_agent.commands.chat.ConversationStore",
            return_value=mock_store,
        )

        # Mock get_resolved_model_name
        mocker.patch(
            "github_agent.commands.chat.get_resolved_model_name",
            return_value="qwen3:8b",
        )

        # Mock UUID generation for predictability
        test_uuid = "test-uuid-1234"
        mocker.patch("github_agent.commands.chat.uuid.uuid4", return_value=test_uuid)

        mock_graph = mocker.MagicMock()
        mock_create_graph.return_value = mock_graph

        # Execute chat command
        chat(model_name=None)

        # Verify conversation was created
        conversation = mock_store.get_conversation(test_uuid)
        assert conversation is not None, "Expected conversation to exist"
        assert conversation["thread_id"] == test_uuid
        assert conversation["command"] == "chat"
        assert conversation["summary"] == "Interactive chat session"
        assert conversation["model_name"] == "qwen3:8b"

        # Verify interactive session was started
        mock_run_session.assert_called_once_with(mock_graph, test_uuid)

    def test_uses_custom_model_name(self, mock_store, mocker):
        """Test that chat command respects custom model_name."""
        # Mock dependencies
        mocker.patch("github_agent.commands.chat.run_interactive_session")
        mock_create_graph = mocker.patch(
            "github_agent.commands.chat.create_configured_agent"
        )

        mocker.patch(
            "github_agent.commands.chat.ConversationStore",
            return_value=mock_store,
        )
        mocker.patch(
            "github_agent.commands.chat.get_resolved_model_name",
            return_value="claude-3-opus-20240229",
        )

        test_uuid = "test-uuid-5678"
        mocker.patch("github_agent.commands.chat.uuid.uuid4", return_value=test_uuid)

        mock_graph = mocker.MagicMock()
        mock_create_graph.return_value = mock_graph

        # Execute with custom model
        chat(model_name="claude-3-opus-20240229")

        # Verify model_name was stored
        conversation = mock_store.get_conversation(test_uuid)
        assert conversation is not None, "Expected conversation to exist"
        assert conversation["model_name"] == "claude-3-opus-20240229"

        # Verify graph was created with custom model
        mock_create_graph.assert_called_once_with("claude-3-opus-20240229")


class TestResumeCommand:
    """Tests for the resume command (after refactoring)."""

    def test_resumes_existing_conversation(self, mock_store, mocker):
        """Test that resume command works with existing conversation.

        Note: Messages are now persisted by LangGraph's SqliteSaver,
        not in ConversationStore.
        """
        # Mock dependencies
        mock_run_session = mocker.patch(
            "github_agent.commands.runners.run_interactive_session"
        )
        mock_create_graph = mocker.patch(
            "github_agent.commands.runners.create_configured_agent"
        )

        thread_id = str(uuid.uuid4())
        mock_store.create_conversation(
            thread_id, "chat", "Previous session", model_name="qwen3:8b"
        )

        mocker.patch(
            "github_agent.commands.runners.ConversationStore",
            return_value=mock_store,
        )

        mock_graph = mocker.MagicMock()
        mock_create_graph.return_value = mock_graph

        # Execute resume using core function
        resume_conversation(thread_id=thread_id, model_name=None)

        # Verify interactive session was started
        mock_run_session.assert_called_once_with(mock_graph, thread_id)

    def test_fails_on_nonexistent_conversation(self, mock_store, mocker):
        """Test that resume fails gracefully for nonexistent conversation."""
        mocker.patch(
            "github_agent.commands.runners.ConversationStore",
            return_value=mock_store,
        )

        # Execute resume with nonexistent thread and expect LookupError
        with pytest.raises(LookupError):
            resume_conversation(thread_id="nonexistent-thread", model_name=None)

    def test_fails_when_both_thread_id_and_last_specified(self, mock_store, mocker):
        """Test that resume fails when both thread_id and last are specified."""
        mocker.patch(
            "github_agent.commands.runners.ConversationStore",
            return_value=mock_store,
        )

        # Execute resume with both thread_id and last=True
        with pytest.raises(ValueError, match="Cannot specify both"):
            resume_conversation(thread_id="some-thread", last=True, model_name=None)

    def test_fails_when_neither_thread_id_nor_last_specified(self, mock_store, mocker):
        """Test that resume fails when neither thread_id nor last are specified."""
        mocker.patch(
            "github_agent.commands.runners.ConversationStore",
            return_value=mock_store,
        )

        # Execute resume with neither argument
        with pytest.raises(ValueError, match="Must specify either"):
            resume_conversation(model_name=None)


class TestIntegration:
    """Integration tests for chat and resume workflow."""

    def test_chat_creates_resumable_conversation(self, mock_store, mocker):
        """Test that a chat session can be resumed later.

        Note: Messages are now persisted by LangGraph's SqliteSaver,
        so we verify the conversation metadata exists and can be resumed.
        """
        # Setup mocks — chat() and resume_conversation() now live in separate
        # modules, so patch both.
        mock_create_graph_chat = mocker.patch(
            "github_agent.commands.chat.create_configured_agent"
        )
        mock_create_graph_runners = mocker.patch(
            "github_agent.commands.runners.create_configured_agent"
        )

        mock_graph = mocker.MagicMock()
        mock_graph.astream_events = empty_async_iter
        mock_create_graph_chat.return_value = mock_graph
        mock_create_graph_runners.return_value = mock_graph

        mocker.patch(
            "github_agent.commands.chat.ConversationStore", return_value=mock_store
        )
        mocker.patch(
            "github_agent.commands.runners.ConversationStore", return_value=mock_store
        )
        mocker.patch(
            "github_agent.commands.chat.get_resolved_model_name",
            return_value="qwen3:8b",
        )

        test_uuid = str(uuid.uuid4())
        mocker.patch("github_agent.commands.chat.uuid.uuid4", return_value=test_uuid)

        # Mock user input for chat session
        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = ["Hello from chat", "exit"]

        # Execute chat command
        chat(model_name=None)

        # Verify conversation metadata was created
        conversation = mock_store.get_conversation(test_uuid)
        assert conversation is not None
        assert conversation["thread_id"] == test_uuid
        assert conversation["command"] == "chat"

        # Now resume the conversation
        mock_input.side_effect = ["Hello from resume", "exit"]

        # Should not raise exception
        resume_conversation(thread_id=test_uuid, model_name=None)

        # Verify conversation still exists
        conversation = mock_store.get_conversation(test_uuid)
        assert conversation is not None, "Expected conversation to exist"
