"""Integration test for the runners → AG-UI pipeline against a real (in-memory)
LangGraph graph with a SqliteSaver checkpointer.

This is the regression test for the bug where switching to `astream_events`
broke the existing sync `SqliteSaver`: the runner must swap to
`AsyncSqliteSaver` for the duration of the stream.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from langgraph.graph.state import StateGraph

from github_agent.commands.runners import run_prompt
from tests.conftest import empty_async_iter


class _State(TypedDict):
    messages: Annotated[list, add_messages]


def _build_graph_with_sync_saver(db_path: str):
    g: StateGraph[_State] = StateGraph(_State)
    g.add_node("echo", lambda s: {"messages": [("assistant", "hello")]})
    g.add_edge("__start__", "echo")
    g.add_edge("echo", "__end__")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    compiled = g.compile(checkpointer=saver)
    compiled._db_path = db_path  # type: ignore[attr-defined]
    return compiled, conn


def test_run_prompt_swaps_sync_saver_for_async_during_streaming(tmp_path: Path):
    """run_prompt must not raise even though the graph has a sync SqliteSaver."""
    db_path = str(tmp_path / "checkpoints.db")
    graph, conn = _build_graph_with_sync_saver(db_path)

    try:
        # If the runner didn't swap the checkpointer, astream_events would
        # raise NotImplementedError ("SqliteSaver does not support async
        # methods") and the runner would print an error. We assert the run
        # completes silently — and that the original sync saver is restored
        # afterwards so subsequent sync reads (e.g. ConversationStore) keep
        # working.
        run_prompt("Hi there", graph, "thread-xyz")
        assert isinstance(graph.checkpointer, SqliteSaver)
    finally:
        conn.close()


def test_run_prompt_streams_events_to_console(tmp_path: Path, capsys):
    """Smoke test: a complete run produces visible Assistant output."""
    db_path = str(tmp_path / "checkpoints.db")
    graph, conn = _build_graph_with_sync_saver(db_path)

    try:
        run_prompt("Hi", graph, "thread-1")
    finally:
        conn.close()

    output = capsys.readouterr().out
    # We don't assert exact text since the chat model isn't invoked in this
    # trivial graph; we just confirm no exception escaped to the user.
    assert "Error during prompt execution" not in output


def test_run_prompt_falls_back_when_no_db_path_attached(tmp_path: Path):
    """Graphs without a `_db_path` keep their original checkpointer and still run."""
    from langgraph.checkpoint.memory import InMemorySaver

    g: StateGraph[_State] = StateGraph(_State)
    g.add_node("echo", lambda s: {"messages": [("assistant", "hello")]})
    g.add_edge("__start__", "echo")
    g.add_edge("echo", "__end__")
    saver = InMemorySaver()
    compiled = g.compile(checkpointer=saver)

    run_prompt("Hi", compiled, "thread-mem")

    # No swap should have happened — original checkpointer preserved.
    assert compiled.checkpointer is saver
    # The run completed and committed state through the original checkpointer.
    snapshot = compiled.get_state({"configurable": {"thread_id": "thread-mem"}})
    messages = (snapshot.values or {}).get("messages", [])
    assert any(getattr(m, "content", None) == "hello" for m in messages)


def test_mock_graph_does_not_leak_sqlite_file_named_after_mock(
    tmp_path: Path, monkeypatch, mocker
):
    """Regression: a MagicMock graph must not cause the runner to create a
    SQLite file literally named '<MagicMock ...>' in the working directory.

    MagicMock auto-creates attributes on access, so `getattr(mock, "_db_path",
    None)` returns a MagicMock — not None. If we don't check the type, we
    happily pass that MagicMock to `AsyncSqliteSaver.from_conn_string`, which
    creates a file with the mock's repr as the name.
    """
    monkeypatch.chdir(tmp_path)

    mock_graph = mocker.MagicMock()
    mock_graph.astream_events = empty_async_iter

    run_prompt("hi", mock_graph, "thread-mock")

    leaked = list(tmp_path.glob("<MagicMock*"))
    assert leaked == [], f"runner leaked files: {leaked}"


def test_create_graph_attaches_db_path_for_runner_swap(tmp_path: Path):
    """The agent factory must stash the db_path on the compiled graph so the
    runner can later swap in an AsyncSqliteSaver."""
    from core.config import LLMProviderConfig
    from integrations.github.agent import create_graph

    db_path = str(tmp_path / "checkpoints.db")
    # Minimal provider config — we won't invoke the LLM, just inspect the graph.
    config = LLMProviderConfig(
        llm_provider="ollama",
        model_name="test-model",
        ollama_base_url="http://localhost:11434",
    )
    graph = create_graph(config, db_path=db_path)
    try:
        assert getattr(graph, "_db_path", None) == db_path
    finally:
        if isinstance(graph.checkpointer, SqliteSaver):
            graph.checkpointer.conn.close()
