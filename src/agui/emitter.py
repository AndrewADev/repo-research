"""Translate LangChain v2 stream events into AG-UI protocol events.

The emitter is the single point in the codebase that imports LangChain/LangGraph
types. Every renderer (TUI, Gradio, SSE) consumes only `ag_ui.core` events.
"""

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any
from uuid import uuid4

from ag_ui.core import (
    BaseEvent,
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
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph


def _extract_text(content: Any) -> str:
    """Pull plain text out of a LangChain message content payload.

    Content may be a str (Ollama, HuggingFace) or a list of blocks (Anthropic
    returns [{"type": "text", "text": "..."}, ...]).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, Mapping) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


async def emit_agui_events(
    graph: CompiledStateGraph,
    state: Mapping[str, Any],
    config: RunnableConfig,
) -> AsyncIterator[BaseEvent]:
    """Stream a graph run and yield AG-UI events.

    The LangGraph graph is invoked via `astream_events(version="v2")`, which
    surfaces token-level chat-model deltas and tool boundaries. Each LangChain
    event is mapped to zero or more AG-UI events; non-essential events (chain
    starts/ends for inner nodes, retriever events, etc.) are dropped.
    """
    thread_id = str(config.get("configurable", {}).get("thread_id") or uuid4())
    run_id = str(uuid4())

    root_run_id: str | None = None
    open_text_messages: dict[str, str] = {}  # message_id → accumulated emitted text
    open_tool_calls: dict[str, str] = {}
    last_assistant_message_id: str | None = None

    yield RunStartedEvent(thread_id=thread_id, run_id=run_id)

    try:
        async for event in graph.astream_events(
            state, config=dict(config), version="v2"
        ):
            kind = event.get("event")
            data = event.get("data") or {}
            ev_run_id = str(event.get("run_id") or "")

            if kind == "on_chain_start" and root_run_id is None:
                root_run_id = ev_run_id
                continue

            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk is None:
                    continue

                message_id = ev_run_id or str(uuid4())
                text = _extract_text(getattr(chunk, "content", ""))
                if text:
                    if message_id not in open_text_messages:
                        open_text_messages[message_id] = ""
                        last_assistant_message_id = message_id
                        yield TextMessageStartEvent(message_id=message_id)
                    open_text_messages[message_id] += text
                    yield TextMessageContentEvent(message_id=message_id, delta=text)

                for tcc in getattr(chunk, "tool_call_chunks", None) or []:
                    tc_id = tcc.get("id") or ""
                    if not tc_id:
                        continue
                    if tc_id not in open_tool_calls:
                        name = tcc.get("name") or ""
                        open_tool_calls[tc_id] = name
                        yield ToolCallStartEvent(
                            tool_call_id=tc_id,
                            tool_call_name=name,
                            parent_message_id=message_id,
                        )
                    args_delta = tcc.get("args") or ""
                    if args_delta:
                        yield ToolCallArgsEvent(tool_call_id=tc_id, delta=args_delta)
                continue

            if kind == "on_chat_model_end":
                message = data.get("output")
                message_id = ev_run_id

                content_text = _extract_text(getattr(message, "content", ""))
                tool_calls = getattr(message, "tool_calls", None) or []

                if message_id not in open_text_messages and content_text:
                    # No streaming — emit whole message as one delta.
                    open_text_messages[message_id] = ""
                    last_assistant_message_id = message_id
                    yield TextMessageStartEvent(message_id=message_id)
                    yield TextMessageContentEvent(
                        message_id=message_id, delta=content_text
                    )
                    open_text_messages[message_id] = content_text
                elif message_id in open_text_messages and content_text:
                    # Streaming happened — flush any tail chunks missed.
                    streamed = open_text_messages[message_id]
                    if content_text != streamed and len(content_text) > len(streamed):
                        tail = content_text[len(streamed) :]
                        yield TextMessageContentEvent(message_id=message_id, delta=tail)
                        open_text_messages[message_id] = content_text

                # Close intermediate (tool-calling) messages now; defer the
                # final one so post-stream reconciliation can flush from state.
                if tool_calls and message_id in open_text_messages:
                    yield TextMessageEndEvent(message_id=message_id)
                    open_text_messages.pop(message_id, None)

                for tc in tool_calls:
                    tc_id = tc.get("id") or ""
                    if not tc_id or tc_id in open_tool_calls:
                        continue
                    name = tc.get("name") or ""
                    args = tc.get("args") or {}
                    open_tool_calls[tc_id] = name
                    yield ToolCallStartEvent(
                        tool_call_id=tc_id,
                        tool_call_name=name,
                        parent_message_id=message_id,
                    )
                    yield ToolCallArgsEvent(tool_call_id=tc_id, delta=json.dumps(args))
                continue

            if kind == "on_tool_end":
                output = data.get("output")
                tool_call_id = (
                    getattr(output, "tool_call_id", None)
                    or event.get("metadata", {}).get("tool_call_id")
                    or ""
                )
                if tool_call_id and tool_call_id in open_tool_calls:
                    content = _extract_text(getattr(output, "content", ""))
                    if not content and output is not None:
                        content = str(output)
                    yield ToolCallResultEvent(
                        message_id=str(uuid4()),
                        tool_call_id=tool_call_id,
                        content=content,
                    )
                    yield ToolCallEndEvent(tool_call_id=tool_call_id)
                    open_tool_calls.pop(tool_call_id, None)
                continue

    except Exception as exc:  # pragma: no cover - exercised via tests
        # raw_event carries the original exception for in-process callers
        # (CLI runner reads HTTP body / traceback off it). Wire transports
        # should ignore it.
        yield RunErrorEvent(message=str(exc), code=type(exc).__name__, raw_event=exc)
        return

    # LangChain's async wrapper over sync `.invoke()` can deliver truncated
    # on_chat_model_* payloads while the AIMessage committed to state is
    # complete. Flush any missing tail from state. Only when streamed text is
    # a clean prefix — otherwise appending would mangle what the user saw.
    if last_assistant_message_id is not None:
        authoritative = await _final_assistant_text(graph, config)
        streamed = open_text_messages.get(last_assistant_message_id, "")
        if authoritative.startswith(streamed) and len(authoritative) > len(streamed):
            tail = authoritative[len(streamed) :]
            yield TextMessageContentEvent(
                message_id=last_assistant_message_id, delta=tail
            )
            open_text_messages[last_assistant_message_id] = authoritative

    for message_id in list(open_text_messages):
        yield TextMessageEndEvent(message_id=message_id)
    for tc_id in list(open_tool_calls):
        yield ToolCallEndEvent(tool_call_id=tc_id)

    yield RunFinishedEvent(thread_id=thread_id, run_id=run_id)


async def _final_assistant_text(
    graph: CompiledStateGraph, config: RunnableConfig
) -> str:
    """Last AIMessage text from the latest checkpoint, or "" on failure."""
    try:
        snapshot = await graph.aget_state(dict(config))
    except Exception:
        return ""
    values = getattr(snapshot, "values", None)
    if not isinstance(values, dict):
        return ""
    for msg in reversed(values.get("messages", [])):
        if isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai":
            return _extract_text(getattr(msg, "content", ""))
    return ""
