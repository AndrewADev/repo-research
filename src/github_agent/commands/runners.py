import asyncio
import os
import traceback
from typing import Any

from ag_ui.core import RunErrorEvent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph
from rich.console import Console
from rich.markup import escape as rich_escape

from agui import emit_agui_events, render_to_console
from core.models import TemplatedPrompt
from integrations.github.agent import close_agent_resources, create_configured_agent
from integrations.github.models import GitHubToolState, get_empty_state
from storage import ConversationStore, default_db_path

console = Console()

DEBUG_ENV_VAR = "GITHUB_AGENT_DEBUG"


def print_prompt_header(prompt_text: str) -> None:
    console.print("[bold cyan]📋 Prompt:[/bold cyan]")
    console.print(prompt_text, highlight=False)
    console.print()


def run_templated_prompt(
    prompt: TemplatedPrompt,
    user_args: list[str],
    graph: CompiledStateGraph[GitHubToolState],
    thread_id: str,
    *,
    db_path: str | None = None,
):
    call_args = {}

    # Handle the case where we have multiple user args but only one template key
    # (e.g., multiple topics passed as comma-separated list)
    if len(prompt.keys) == 1 and len(user_args) > 1:
        # Join all arguments with commas for the single key
        key = prompt.keys[0]
        call_args[key] = ", ".join(user_args)
    else:
        # Original 1:1 mapping for multiple keys
        for i, key in enumerate(prompt.keys):
            if i < len(user_args):
                call_args[key] = user_args[i]
            else:
                call_args[key] = ""  # Default to empty string if not enough args

    # Format the template with the provided arguments
    formatted_prompt = prompt.template.format(**call_args)

    # Build a display-only version with template values bolded so the user can
    # see which parts of the prompt came from their flags vs. the static text.
    display_args = {k: f"[bold]{rich_escape(v)}[/bold]" for k, v in call_args.items()}
    print_prompt_header(prompt.template.format(**display_args))

    run_prompt(formatted_prompt, graph, thread_id, db_path=db_path)


def _summarize_message(msg: Any) -> str:
    """One-line debug description of a graph message: type, name, sizes, tool refs."""
    cls = type(msg).__name__
    parts = [cls]
    name = getattr(msg, "name", None)
    if name:
        parts.append(f"name={name}")
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        names = [
            (tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "?"))
            for tc in tool_calls
        ]
        parts.append(f"tool_calls={names}")
    tool_call_id = getattr(msg, "tool_call_id", None)
    if tool_call_id:
        parts.append(f"tool_call_id={tool_call_id[:8]}…")
    content = getattr(msg, "content", None)
    if content is None:
        parts.append("content=None")
    elif isinstance(content, str):
        parts.append(f"content_len={len(content)}")
    else:
        parts.append(f"content_type={type(content).__name__}")
    return f"<{' '.join(parts)}>"


def _format_recent_messages(event: dict | None, n: int = 4) -> str:
    if not event or "messages" not in event or not event["messages"]:
        return "(no messages in last graph event)"
    msgs = event["messages"][-n:]
    return "\n    ".join(_summarize_message(m) for m in msgs)


def _report_prompt_error(e: Exception, last_event: dict | None) -> None:
    """Surface as much actionable detail as possible from a graph.stream failure."""
    debug = bool(os.environ.get(DEBUG_ENV_VAR))

    console.print()
    console.print("[bold red]Error during prompt execution[/bold red]")
    exc_type = f"{type(e).__module__}.{type(e).__name__}"
    console.print(f"  [bold]Exception:[/bold] {exc_type}")
    message = str(e) or "(empty message)"
    console.print(f"  [bold]Message:[/bold] {rich_escape(message)}")

    # If this is a requests/HfHubHTTPError-shaped exception, the HTTP body is
    # where the real diagnostic lives. str(e) often discards it.
    response = getattr(e, "response", None)
    if response is not None:
        status = getattr(response, "status_code", "?")
        try:
            body = response.text
        except Exception:  # pragma: no cover - defensive
            body = "(response.text unreadable)"
        console.print(f"  [bold]HTTP status:[/bold] {status}")
        console.print(f"  [bold]HTTP body:[/bold] {rich_escape(body) or '(empty)'}")

    # Show the graph state at the point of failure so we can correlate the
    # error with which step / which tool round-trip blew up.
    console.print(
        f"  [bold]Recent messages:[/bold]\n    {_format_recent_messages(last_event)}"
    )

    if debug:
        console.print("\n[bold]Traceback:[/bold]")
        traceback.print_exc()
    else:
        console.print(f"\n  (Set [bold]{DEBUG_ENV_VAR}=1[/bold] for full traceback.)")


async def _stream_through_agui(
    state: GitHubToolState,
    graph: CompiledStateGraph[GitHubToolState],
    config: RunnableConfig,
    db_path: str,
) -> RunErrorEvent | None:
    """Drive the graph via `astream_events` under an AsyncSqliteSaver.

    If the caller pre-attached a checkpointer (e.g. InMemorySaver in tests),
    use it as-is; otherwise claim an AsyncSqliteSaver for the run.
    """
    if graph.checkpointer is not None:
        events = emit_agui_events(graph, state, config)
        return await render_to_console(events, console)

    async with AsyncSqliteSaver.from_conn_string(db_path) as async_saver:
        graph.checkpointer = async_saver
        try:
            events = emit_agui_events(graph, state, config)
            return await render_to_console(events, console)
        finally:
            graph.checkpointer = None


def _exception_from_error_event(event: RunErrorEvent) -> Exception:
    """Recover a usable exception from a `RunErrorEvent`.

    The emitter stashes the original exception in `raw_event` so HTTP body /
    traceback are preserved across the protocol boundary; fall back to a
    plain `RuntimeError` if it wasn't preserved (e.g. event came from a
    remote source).
    """
    original = getattr(event, "raw_event", None)
    if isinstance(original, Exception):
        return original
    return RuntimeError(event.message)


def _handle_run_outcome(
    error_event: RunErrorEvent | None,
    graph: CompiledStateGraph[GitHubToolState],
    config: RunnableConfig,
    db_path: str,
) -> None:
    if error_event is None:
        return
    _report_prompt_error(
        _exception_from_error_event(error_event),
        _fetch_last_event(graph, config, db_path),
    )


def _fetch_last_event(
    graph: CompiledStateGraph[GitHubToolState],
    config: RunnableConfig,
    db_path: str,
) -> dict | None:
    """Read the latest checkpoint state for diagnostics.

    Called from sync error paths after the AsyncSqliteSaver was detached, so
    we open a short-lived sync SqliteSaver against the same file. If the graph
    has a checkpointer attached (test InMemorySaver), use that instead.
    """
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    try:
        if graph.checkpointer is None:
            with sqlite3.connect(db_path) as conn:
                graph.checkpointer = SqliteSaver(conn)
                try:
                    snapshot = graph.get_state(config)
                finally:
                    graph.checkpointer = None
        else:
            snapshot = graph.get_state(config)
    except Exception:  # pragma: no cover - mock graphs / missing checkpointer
        return None
    values = getattr(snapshot, "values", None)
    return dict(values) if isinstance(values, dict) else None


def run_prompt(
    formatted_prompt: str,
    graph: CompiledStateGraph[GitHubToolState],
    thread_id: str,
    *,
    db_path: str | None = None,
):
    db_path = db_path or default_db_path()
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    state = get_empty_state(messages=[HumanMessage(content=formatted_prompt)])

    try:
        error_event = asyncio.run(_stream_through_agui(state, graph, config, db_path))
    except Exception as e:
        _report_prompt_error(e, _fetch_last_event(graph, config, db_path))
    else:
        _handle_run_outcome(error_event, graph, config, db_path)


def run_interactive_session(
    graph: CompiledStateGraph[GitHubToolState],
    thread_id: str,
    *,
    db_path: str | None = None,
):
    """Run an interactive chat session."""
    db_path = db_path or default_db_path()
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    # Interactive loop
    print("💬 Interactive mode (type 'exit' or 'quit' to end)\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 Ending conversation.")
                break

            if not user_input:
                continue

            state: GitHubToolState = {"messages": [("user", user_input)]}  # type: ignore[typeddict-item]
            try:
                error_event = asyncio.run(
                    _stream_through_agui(state, graph, config, db_path)
                )
            except Exception as e:
                _report_prompt_error(e, _fetch_last_event(graph, config, db_path))
            else:
                _handle_run_outcome(error_event, graph, config, db_path)

        except KeyboardInterrupt:
            print("\n\n👋 Ending conversation.")
            break
        except EOFError:
            print("\n👋 Ending conversation.")
            break


def resume_conversation(
    thread_id: str | None = None,
    last: bool = False,
    model_name: str | None = None,
):
    """Core logic for resuming a conversation."""
    with ConversationStore() as store:
        if thread_id and last:
            raise ValueError("Cannot specify both thread_id and last flag")

        if not thread_id and not last:
            raise ValueError("Must specify either thread_id or last flag")

        if last:
            recent = store.get_most_recent_conversation()
            if recent is None:
                raise LookupError("No conversations found")
            thread_id = recent["thread_id"]
            print(f"📌 Using most recent conversation: {thread_id}")

        conversation = store.get_conversation(thread_id)
        if conversation is None:
            raise LookupError(f"Conversation {thread_id} not found")

        print(f"\n🔄 Resuming conversation: {thread_id}")
        print(f"Command: {conversation['command']}")

        if model_name is None:
            model_name = conversation.get("model_name")
            if model_name:
                print(f"Model: {model_name} (from conversation)")
            else:
                print("Model: Using default")
        else:
            print(f"Model: {model_name} (overridden)")

        if conversation["summary"]:
            print(f"Summary: {conversation['summary']}")
        print(f"Messages: {len(conversation['messages'])}\n")

        agent = create_configured_agent(model_name)
        try:
            run_interactive_session(agent, thread_id)
        finally:
            close_agent_resources(agent)


__all__ = [
    "print_prompt_header",
    "run_prompt",
    "run_templated_prompt",
    "run_interactive_session",
    "resume_conversation",
]
