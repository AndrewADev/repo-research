"""Tests for prompt execution flow (run_templated_prompt and run_prompt)."""

import uuid

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import PromptTemplate

from core.models import TemplatedPrompt
from github_agent.commands.runners import (
    _format_recent_messages,
    _report_prompt_error,
    _summarize_message,
)
from github_agent.main import run_templated_prompt
from tests.conftest import raising_async_iter, recording_async_iter


class TestRunTemplatedPrompt:
    """Tests for run_templated_prompt argument mapping and execution."""

    def test_special_characters_in_values(self, mocker):
        """Test that special characters in argument values are handled correctly."""
        prompt = TemplatedPrompt(
            template=PromptTemplate.from_template("Query: {query}"),
            keys=["query"],
        )

        astream, calls = recording_async_iter()
        mock_graph = mocker.MagicMock()
        mock_graph.astream_events = astream

        thread_id = str(uuid.uuid4())

        special_values = [
            "search \"quotes\" and 'apostrophes'",
            "newlines\nand\ttabs",
            "unicode: 万歳 🎉",
            "symbols: @#$%^&*()",
        ]

        for value in special_values:
            calls.clear()
            run_templated_prompt(prompt, [value], mock_graph, thread_id)

            assert calls, "expected astream_events to be called"
            state = calls[0]["args"][0]
            assert value in state["messages"][0].content

    def test_graph_exception_handling(self, mocker, capsys):
        """Test that exceptions during graph execution are caught and reported."""
        prompt = TemplatedPrompt(
            template=PromptTemplate.from_template("Test: {key}"),
            keys=["key"],
        )

        # emit_agui_events catches the exception and emits a RunErrorEvent;
        # the renderer surfaces it as an "Error:" line in stdout.
        mock_graph = mocker.MagicMock()
        mock_graph.astream_events = raising_async_iter(
            RuntimeError("Graph execution failed")
        )

        thread_id = str(uuid.uuid4())

        # Should not raise; the renderer prints an "Error:" line.
        run_templated_prompt(prompt, ["value"], mock_graph, thread_id)

        # Verify error was printed
        captured = capsys.readouterr()
        assert "Error during prompt execution" in captured.out
        assert "Graph execution failed" in captured.out


class _FakeResponse:
    """Minimal duck-typed stand-in for requests.Response / HfHubHTTPError.response."""

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class TestErrorReporting:
    """Coverage for _report_prompt_error and its supporting helpers."""

    def test_summarize_message_for_ai_with_tool_calls(self):
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_starred_repositories",
                    "args": {},
                    "id": "call_abc",
                    "type": "tool_call",
                }
            ],
        )
        summary = _summarize_message(msg)
        assert "AIMessage" in summary
        assert "get_starred_repositories" in summary

    def test_summarize_message_for_tool_message(self):
        msg = ToolMessage(
            content='{"results": []}',
            tool_call_id="call_abcdef1234",
            name="get_starred_repositories",
        )
        summary = _summarize_message(msg)
        assert "ToolMessage" in summary
        assert "name=get_starred_repositories" in summary
        assert "tool_call_id=call_abc" in summary  # truncated to 8 chars
        assert "content_len=15" in summary

    def test_format_recent_messages_empty(self):
        assert "no messages" in _format_recent_messages(None)
        assert "no messages" in _format_recent_messages({"messages": []})

    def test_report_surfaces_http_body_from_response(self, capsys, monkeypatch):
        monkeypatch.delenv("GITHUB_AGENT_DEBUG", raising=False)

        err = RuntimeError("(Request ID: Root=1-abc;xyz)\n\nBad request:\n")
        err.response = _FakeResponse(  # type: ignore[attr-defined]
            status_code=400,
            text='{"error":"Input validation error: tool_call_id mismatch"}',
        )

        _report_prompt_error(err, last_event=None)

        out = capsys.readouterr().out
        assert "Error during prompt execution" in out
        assert "RuntimeError" in out  # exception type surfaced
        assert "HTTP status:" in out and "400" in out
        assert "tool_call_id mismatch" in out  # the body we previously lost
        assert "GITHUB_AGENT_DEBUG=1" in out  # debug hint shown when off

    def test_report_includes_recent_message_context(self, capsys, monkeypatch):
        monkeypatch.delenv("GITHUB_AGENT_DEBUG", raising=False)

        event = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_starred_repositories",
                            "args": {},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content='{"results": [{"name": "x/y"}]}',
                    tool_call_id="call_1",
                    name="get_starred_repositories",
                ),
            ]
        }

        _report_prompt_error(RuntimeError("boom"), last_event=event)

        out = capsys.readouterr().out
        assert "Recent messages:" in out
        assert "AIMessage" in out
        assert "ToolMessage" in out
        assert "get_starred_repositories" in out

    def test_report_traceback_only_when_debug_env_set(self, capsys, monkeypatch):
        monkeypatch.setenv("GITHUB_AGENT_DEBUG", "1")
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            _report_prompt_error(e, last_event=None)
        out = capsys.readouterr().out
        assert "Traceback:" in out
        assert "GITHUB_AGENT_DEBUG=1" not in out  # hint suppressed when already on
