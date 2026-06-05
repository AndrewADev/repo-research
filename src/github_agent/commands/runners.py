import os
import traceback
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from rich.console import Console
from rich.markup import escape as rich_escape

from core.models import TemplatedPrompt
from integrations.github.agent import close_agent_resources, create_configured_agent
from integrations.github.models import GitHubToolState, get_empty_state
from storage import ConversationStore

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

    run_prompt(formatted_prompt, graph, thread_id)


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


def run_prompt(
    formatted_prompt: str,
    graph: CompiledStateGraph[GitHubToolState],
    thread_id: str,
):
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    # Run the formatted prompt through the graph
    # LangGraph's SqliteSaver will automatically persist all messages
    last_event: dict | None = None
    try:
        events = graph.stream(
            get_empty_state(messages=[HumanMessage(content=formatted_prompt)]),
            config,
            stream_mode="values",
        )

        for event in events:
            last_event = event
            if "messages" in event:
                last_message = event["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    continue
                print(f"Response: {last_message.content}\n")

    except Exception as e:
        _report_prompt_error(e, last_event)


def run_interactive_session(graph: CompiledStateGraph[GitHubToolState], thread_id: str):
    """Run an interactive chat session.

    Args:
        graph: Configured LangGraph instance
        thread_id: Thread identifier for the conversation
        store: ConversationStore instance (for metadata only)
    """
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

            # Stream response
            # LangGraph's SqliteSaver will automatically persist all messages
            events = graph.stream(
                {"messages": [("user", user_input)]},
                config,
                stream_mode="values",
            )

            print("\nAssistant: ", end="", flush=True)
            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]
                    if hasattr(last_message, "content"):
                        print(last_message.content)

            print()

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
    """Core logic for resuming a conversation.

    Args:
        thread_id: Thread ID to resume
        last: Whether to resume the most recent conversation
        model_name: Optional model name override

    Raises:
        ValueError: If arguments are invalid
        LookupError: If conversation not found
    """
    with ConversationStore() as store:
        # Validate arguments
        if thread_id and last:
            raise ValueError("Cannot specify both thread_id and last flag")

        if not thread_id and not last:
            raise ValueError("Must specify either thread_id or last flag")

        # Get thread_id from most recent conversation if --last is used
        if last:
            recent = store.get_most_recent_conversation()
            if recent is None:
                raise LookupError("No conversations found")
            thread_id = recent["thread_id"]
            print(f"📌 Using most recent conversation: {thread_id}")

        # Show conversation summary
        conversation = store.get_conversation(thread_id)
        if conversation is None:
            raise LookupError(f"Conversation {thread_id} not found")

        print(f"\n🔄 Resuming conversation: {thread_id}")
        print(f"Command: {conversation['command']}")

        # Use stored model_name unless overridden
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

        # Create graph with the determined model
        agent = create_configured_agent(model_name)
        try:
            # Run interactive session
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
