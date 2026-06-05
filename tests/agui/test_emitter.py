"""Tests for the LangChain → AG-UI event emitter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from ag_ui.core import (
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

from agui.emitter import emit_agui_events


async def _drain(events: AsyncIterator) -> list:
    return [e async for e in events]


def _make_graph(stream_items: list[dict[str, Any]] | Exception) -> Any:
    """Build a fake CompiledStateGraph whose astream_events yields the items."""

    async def _stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        if isinstance(stream_items, Exception):
            raise stream_items
        for item in stream_items:
            yield item

    graph = MagicMock()
    graph.astream_events = _stream
    return graph


def _ai_message(
    content: str = "", tool_calls: list[dict[str, Any]] | None = None
) -> Any:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


def _tool_result(content: str, tool_call_id: str) -> Any:
    out = MagicMock()
    out.content = content
    out.tool_call_id = tool_call_id
    return out


@pytest.mark.asyncio
async def test_emitter_wraps_run_with_start_and_finish_events() -> None:
    graph = _make_graph([])
    config = {"configurable": {"thread_id": "thread-abc"}}

    events = await _drain(emit_agui_events(graph, {}, config))

    assert isinstance(events[0], RunStartedEvent)
    assert events[0].thread_id == "thread-abc"
    assert isinstance(events[-1], RunFinishedEvent)
    assert events[-1].thread_id == "thread-abc"
    assert events[0].run_id == events[-1].run_id


@pytest.mark.asyncio
async def test_emits_text_message_for_whole_message_chat_model() -> None:
    """Providers that don't stream chunks should still produce a text message."""
    graph = _make_graph(
        [
            {"event": "on_chain_start", "run_id": "root", "data": {}},
            {
                "event": "on_chat_model_end",
                "run_id": "msg-1",
                "data": {"output": _ai_message(content="Hello world")},
            },
        ]
    )

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))
    inner = events[1:-1]

    assert [type(e) for e in inner] == [
        TextMessageStartEvent,
        TextMessageContentEvent,
        TextMessageEndEvent,
    ]
    assert inner[0].message_id == "msg-1"
    assert inner[1].delta == "Hello world"


@pytest.mark.asyncio
async def test_streamed_chunks_emit_content_deltas_once_per_message() -> None:
    """Multiple stream chunks share one Start/End bracket per message_id."""
    chunk_a = MagicMock(content="Hel", tool_call_chunks=[])
    chunk_b = MagicMock(content="lo", tool_call_chunks=[])

    graph = _make_graph(
        [
            {"event": "on_chain_start", "run_id": "root", "data": {}},
            {
                "event": "on_chat_model_stream",
                "run_id": "msg-1",
                "data": {"chunk": chunk_a},
            },
            {
                "event": "on_chat_model_stream",
                "run_id": "msg-1",
                "data": {"chunk": chunk_b},
            },
            {
                "event": "on_chat_model_end",
                "run_id": "msg-1",
                "data": {"output": _ai_message(content="Hello")},
            },
        ]
    )

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))
    inner = events[1:-1]

    assert [type(e) for e in inner] == [
        TextMessageStartEvent,
        TextMessageContentEvent,
        TextMessageContentEvent,
        TextMessageEndEvent,
    ]
    deltas = [e.delta for e in inner if isinstance(e, TextMessageContentEvent)]
    assert deltas == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_end_event_flushes_tail_missed_by_chunk_stream() -> None:
    """Regression: if chunks deliver less than the final message content, the
    on_chat_model_end handler must flush the missing tail as a final delta —
    otherwise the user sees a truncated reply (e.g. "## Activity & " cut mid-
    word because the closing chunks were collapsed into the end event).
    """
    chunk_a = MagicMock(content="Hello ", tool_call_chunks=[])
    chunk_b = MagicMock(content="wor", tool_call_chunks=[])
    # Final message has the full "Hello world!" but only "Hello wor" streamed.

    graph = _make_graph(
        [
            {"event": "on_chain_start", "run_id": "root", "data": {}},
            {
                "event": "on_chat_model_stream",
                "run_id": "msg-1",
                "data": {"chunk": chunk_a},
            },
            {
                "event": "on_chat_model_stream",
                "run_id": "msg-1",
                "data": {"chunk": chunk_b},
            },
            {
                "event": "on_chat_model_end",
                "run_id": "msg-1",
                "data": {"output": _ai_message(content="Hello world!")},
            },
        ]
    )

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))
    deltas = [e.delta for e in events if isinstance(e, TextMessageContentEvent)]

    assert "".join(deltas) == "Hello world!", (
        f"missing text after chunks; got deltas={deltas!r}"
    )


@pytest.mark.asyncio
async def test_emitter_reconciles_against_graph_state_when_stream_truncates() -> None:
    """Regression: when LangChain's async wrapper over a sync `.invoke()`
    emits a truncated `on_chat_model_end` payload (provider streaming bug),
    the AIMessage actually committed to the graph state still holds the full
    text. The emitter must read state at the end of the run and flush any
    missing tail so the user never sees a cut-off response.
    """
    from langchain_core.messages import AIMessage

    truncated = _ai_message(content="## 2. Which project appears to")
    full_text = "## 2. Which project appears to have the most active community?"
    # Use a real AIMessage in state — the emitter's reconciliation uses
    # isinstance(AIMessage) to locate the authoritative reply.
    full = AIMessage(content=full_text)

    graph = _make_graph(
        [
            {"event": "on_chain_start", "run_id": "root", "data": {}},
            {
                "event": "on_chat_model_end",
                "run_id": "msg-1",
                "data": {"output": truncated},
            },
        ]
    )

    # aget_state is what the emitter calls to recover authoritative content.
    async def _aget_state(*_args: Any, **_kwargs: Any) -> Any:
        snap = MagicMock()
        snap.values = {"messages": [full]}
        return snap

    graph.aget_state = _aget_state

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))
    deltas = [e.delta for e in events if isinstance(e, TextMessageContentEvent)]

    assert "".join(deltas) == full_text, (
        f"expected reconciliation against state; got deltas={deltas!r}"
    )


@pytest.mark.asyncio
async def test_whole_message_tool_calls_become_start_args_end_triplet() -> None:
    tool_calls = [
        {
            "id": "call-1",
            "name": "search_repositories",
            "args": {"topic": "langgraph"},
        }
    ]
    graph = _make_graph(
        [
            {"event": "on_chain_start", "run_id": "root", "data": {}},
            {
                "event": "on_chat_model_end",
                "run_id": "msg-1",
                "data": {"output": _ai_message(tool_calls=tool_calls)},
            },
            {
                "event": "on_tool_end",
                "run_id": "tool-run",
                "data": {"output": _tool_result("12 repos", "call-1")},
            },
        ]
    )

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))
    types = [type(e) for e in events]

    # Start, ToolCallStart, ToolCallArgs, ToolCallResult, ToolCallEnd, Finish.
    assert ToolCallStartEvent in types
    assert ToolCallArgsEvent in types
    assert ToolCallResultEvent in types
    assert ToolCallEndEvent in types

    start = next(e for e in events if isinstance(e, ToolCallStartEvent))
    args = next(e for e in events if isinstance(e, ToolCallArgsEvent))
    result = next(e for e in events if isinstance(e, ToolCallResultEvent))

    assert start.tool_call_name == "search_repositories"
    assert start.tool_call_id == "call-1"
    assert json.loads(args.delta) == {"topic": "langgraph"}
    assert result.content == "12 repos"
    assert result.tool_call_id == "call-1"

    # Tool end must follow tool result to make rendering ordering predictable.
    result_idx = next(
        i for i, e in enumerate(events) if isinstance(e, ToolCallResultEvent)
    )
    end_idx = next(i for i, e in enumerate(events) if isinstance(e, ToolCallEndEvent))
    assert end_idx > result_idx


@pytest.mark.asyncio
async def test_streaming_tool_call_chunks_open_and_extend_a_single_call() -> None:
    """When the chat model streams tool_call_chunks, args accumulate as deltas."""
    chunk_open = MagicMock(
        content="",
        tool_call_chunks=[{"id": "call-1", "name": "query_issues", "args": '{"repo":'}],
    )
    chunk_more = MagicMock(
        content="",
        tool_call_chunks=[{"id": "call-1", "name": None, "args": '"foo"}'}],
    )

    graph = _make_graph(
        [
            {"event": "on_chain_start", "run_id": "root", "data": {}},
            {
                "event": "on_chat_model_stream",
                "run_id": "msg-1",
                "data": {"chunk": chunk_open},
            },
            {
                "event": "on_chat_model_stream",
                "run_id": "msg-1",
                "data": {"chunk": chunk_more},
            },
            {
                "event": "on_chat_model_end",
                "run_id": "msg-1",
                "data": {"output": _ai_message()},
            },
        ]
    )

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))
    starts = [e for e in events if isinstance(e, ToolCallStartEvent)]
    args = [e for e in events if isinstance(e, ToolCallArgsEvent)]

    assert len(starts) == 1
    assert starts[0].tool_call_name == "query_issues"
    assert "".join(a.delta for a in args) == '{"repo":"foo"}'


@pytest.mark.asyncio
async def test_exception_during_streaming_emits_run_error() -> None:
    graph = _make_graph(RuntimeError("boom"))

    events = await _drain(emit_agui_events(graph, {}, {"configurable": {}}))

    assert isinstance(events[0], RunStartedEvent)
    assert isinstance(events[-1], RunErrorEvent)
    assert events[-1].message == "boom"
    assert events[-1].code == "RuntimeError"
    # RunFinished must not appear when the run errors.
    assert not any(e.type == EventType.RUN_FINISHED for e in events)
