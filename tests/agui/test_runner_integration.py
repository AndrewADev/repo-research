"""Integration tests for the runners → AG-UI pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from langgraph.graph.state import StateGraph

from repo_research.commands.runners import _fetch_last_event, run_prompt


class _State(TypedDict):
    messages: Annotated[list, add_messages]


def _build_graph():
    g: StateGraph[_State] = StateGraph(_State)
    g.add_node("echo", lambda s: {"messages": [("assistant", "hello")]})
    g.add_edge("__start__", "echo")
    g.add_edge("echo", "__end__")
    return g.compile()


def test_run_prompt_attaches_and_detaches_async_saver(tmp_path: Path):
    db_path = str(tmp_path / "checkpoints.db")
    graph = _build_graph()

    run_prompt("Hi there", graph, "thread-xyz", db_path=db_path)

    assert graph.checkpointer is None


def test_run_prompt_streams_without_error(tmp_path: Path, capsys):
    db_path = str(tmp_path / "checkpoints.db")
    graph = _build_graph()

    run_prompt("Hi", graph, "thread-1", db_path=db_path)

    assert "Error during prompt execution" not in capsys.readouterr().out


def test_run_prompt_honors_caller_supplied_checkpointer(tmp_path: Path):
    from langgraph.checkpoint.memory import InMemorySaver

    g: StateGraph[_State] = StateGraph(_State)
    g.add_node("echo", lambda s: {"messages": [("assistant", "hello")]})
    g.add_edge("__start__", "echo")
    g.add_edge("echo", "__end__")
    saver = InMemorySaver()
    compiled = g.compile(checkpointer=saver)

    run_prompt("Hi", compiled, "thread-mem", db_path=str(tmp_path / "unused.db"))

    assert compiled.checkpointer is saver
    snapshot = compiled.get_state({"configurable": {"thread_id": "thread-mem"}})
    messages = (snapshot.values or {}).get("messages", [])
    assert any(getattr(m, "content", None) == "hello" for m in messages)


def test_create_graph_compiles_without_checkpointer():
    from core.config import LLMProviderConfig
    from integrations.github.agent import create_graph

    config = LLMProviderConfig(
        llm_provider="ollama",
        model_name="test-model",
        ollama_base_url="http://localhost:11434",
    )
    graph = create_graph(config)

    assert graph.checkpointer is None


def test_create_graph_honors_memory_override():
    from langgraph.checkpoint.memory import InMemorySaver

    from core.config import LLMProviderConfig
    from integrations.github.agent import create_graph

    saver = InMemorySaver()
    config = LLMProviderConfig(
        llm_provider="ollama",
        model_name="test-model",
        ollama_base_url="http://localhost:11434",
    )
    graph = create_graph(config, memory=saver)

    assert graph.checkpointer is saver


def test_fetch_last_event_reads_via_fresh_sync_connection(tmp_path: Path):
    db_path = str(tmp_path / "checkpoints.db")
    graph = _build_graph()

    config = {"configurable": {"thread_id": "thread-diag"}}
    run_prompt("Hi", graph, "thread-diag", db_path=db_path)
    assert graph.checkpointer is None

    snapshot = _fetch_last_event(graph, config, db_path)
    assert snapshot is not None
    messages = snapshot.get("messages", [])
    assert any(getattr(m, "content", None) == "hello" for m in messages)
