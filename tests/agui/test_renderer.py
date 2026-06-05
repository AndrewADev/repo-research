"""Tests for the Rich-based AG-UI terminal renderer."""

from __future__ import annotations

import io
from collections.abc import AsyncIterator

import pytest
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
from rich.console import Console

from agui.renderer import render_to_console


async def _aiter(events: list[BaseEvent]) -> AsyncIterator[BaseEvent]:
    for e in events:
        yield e


def _capture_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    # force_terminal=False + no_color makes Rich emit plain text, simpler to assert on.
    return Console(file=buf, force_terminal=False, no_color=True, width=200), buf


@pytest.mark.asyncio
async def test_text_message_round_trip_emits_assistant_label_and_content() -> None:
    console, buf = _capture_console()
    events: list[BaseEvent] = [
        RunStartedEvent(thread_id="t", run_id="r"),
        TextMessageStartEvent(message_id="m1"),
        TextMessageContentEvent(message_id="m1", delta="Hello, "),
        TextMessageContentEvent(message_id="m1", delta="world."),
        TextMessageEndEvent(message_id="m1"),
        RunFinishedEvent(thread_id="t", run_id="r"),
    ]

    await render_to_console(_aiter(events), console)

    output = buf.getvalue()
    assert "Assistant:" in output
    assert "Hello, world." in output


@pytest.mark.asyncio
async def test_tool_call_renders_name_args_and_result_summary() -> None:
    console, buf = _capture_console()
    events: list[BaseEvent] = [
        ToolCallStartEvent(tool_call_id="c1", tool_call_name="search_repositories"),
        ToolCallArgsEvent(tool_call_id="c1", delta='{"topic":"langgraph"}'),
        ToolCallResultEvent(
            message_id="m", tool_call_id="c1", content="12 repos found"
        ),
        ToolCallEndEvent(tool_call_id="c1"),
    ]

    await render_to_console(_aiter(events), console)
    output = buf.getvalue()

    assert "search_repositories(" in output
    assert "langgraph" in output
    assert ")" in output
    assert "← 12 repos found" in output


@pytest.mark.asyncio
async def test_long_tool_args_are_truncated_in_display() -> None:
    console, buf = _capture_console()
    huge = '{"q":"' + ("x" * 500) + '"}'
    events: list[BaseEvent] = [
        ToolCallStartEvent(tool_call_id="c1", tool_call_name="search"),
        ToolCallArgsEvent(tool_call_id="c1", delta=huge),
        ToolCallEndEvent(tool_call_id="c1"),
    ]

    await render_to_console(_aiter(events), console)
    output = buf.getvalue()

    assert "…" in output
    # Truncation cap is 120 — full 500-byte arg must not survive.
    assert "x" * 500 not in output


@pytest.mark.asyncio
async def test_run_error_is_rendered_visibly() -> None:
    console, buf = _capture_console()
    events: list[BaseEvent] = [RunErrorEvent(message="rate limit hit", code="HTTP429")]

    await render_to_console(_aiter(events), console)

    assert "Error:" in buf.getvalue()
    assert "rate limit hit" in buf.getvalue()


@pytest.mark.asyncio
async def test_rich_markup_in_content_is_escaped_not_interpreted() -> None:
    """A delta containing [bold]X[/bold] must appear literally, not stylised."""
    console, buf = _capture_console()
    events: list[BaseEvent] = [
        TextMessageStartEvent(message_id="m1"),
        TextMessageContentEvent(message_id="m1", delta="see [bold]foo[/bold] here"),
        TextMessageEndEvent(message_id="m1"),
    ]

    await render_to_console(_aiter(events), console)

    assert "[bold]foo[/bold]" in buf.getvalue()
