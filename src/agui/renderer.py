"""Rich-based terminal renderer for AG-UI events.

Consumes only `ag_ui.core` types — no LangChain/LangGraph imports — so the same
event stream can be routed through different renderers (Gradio, SSE) without
duplicating display logic.
"""

from collections.abc import AsyncIterator

from ag_ui.core import (
    BaseEvent,
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from rich.console import Console
from rich.markup import escape as rich_escape

_ARGS_PREVIEW_LIMIT = 120
_RESULT_PREVIEW_LIMIT = 80


def _summarize(text: str, limit: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


async def render_to_console(
    events: AsyncIterator[BaseEvent], console: Console
) -> RunErrorEvent | None:
    """Drain an AG-UI event iterator, painting each event to the terminal.

    Returns the last `RunErrorEvent` seen (or `None`), so the caller can
    optionally surface richer Python-side diagnostics (recent state, HTTP
    body, traceback) beyond the minimal inline "Error: ..." line we print
    here for the benefit of consumers that don't add their own.
    """

    tool_args_buffer: dict[str, list[str]] = {}
    tool_names: dict[str, str] = {}
    error_event: RunErrorEvent | None = None

    async for event in events:
        if isinstance(event, TextMessageStartEvent):
            console.print("\n[bold]Assistant:[/bold] ", end="")

        elif isinstance(event, TextMessageContentEvent):
            console.print(
                rich_escape(event.delta),
                end="",
                soft_wrap=True,
                highlight=False,
            )

        elif isinstance(event, TextMessageEndEvent):
            console.print()

        elif isinstance(event, ToolCallStartEvent):
            tool_names[event.tool_call_id] = event.tool_call_name
            tool_args_buffer[event.tool_call_id] = []
            console.print(
                f"\n[dim cyan]→ {rich_escape(event.tool_call_name)}([/dim cyan]",
                end="",
            )

        elif isinstance(event, ToolCallArgsEvent):
            tool_args_buffer.setdefault(event.tool_call_id, []).append(event.delta)

        elif isinstance(event, ToolCallEndEvent):
            args = "".join(tool_args_buffer.pop(event.tool_call_id, []))
            tool_names.pop(event.tool_call_id, None)
            console.print(
                f"[dim]{rich_escape(_summarize(args, _ARGS_PREVIEW_LIMIT))}[/dim]"
                "[dim cyan])[/dim cyan]"
            )

        elif isinstance(event, ToolCallResultEvent):
            preview = _summarize(event.content, _RESULT_PREVIEW_LIMIT)
            if preview:
                console.print(f"[dim]   ← {rich_escape(preview)}[/dim]")

        elif isinstance(event, RunErrorEvent):
            error_event = event
            console.print(f"\n[red]Error:[/red] {rich_escape(event.message)}")

        elif isinstance(event, RunFinishedEvent):
            console.print()

        else:
            # Future event types (StateSnapshot, Step*, Reasoning*, etc.) are
            # not rendered in the TUI yet — drop them silently.
            if event.type not in {
                EventType.RUN_STARTED,
            }:
                continue

    return error_event
