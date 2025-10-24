import uuid
from typing import Literal

import typer
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from core.config import get_resolved_model_name
from core.models import TemplatedPrompt
from core.prompts import (
    hotspot_analysis,
    run_diagnostic,
    starred_pulse,
    topic_prompt,
)
from integrations.github.agent import close_agent_resources, create_configured_agent
from integrations.github.models import GitHubToolState, get_empty_state
from storage import ConversationStore

# Load environment variables
load_dotenv()

app = typer.Typer(rich_markup_mode="rich")


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

    run_prompt(formatted_prompt, graph, thread_id)


def run_prompt(
    formatted_prompt: str,
    graph: CompiledStateGraph[GitHubToolState],
    thread_id: str,
):
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    # Run the formatted prompt through the graph
    # LangGraph's SqliteSaver will automatically persist all messages
    try:
        events = graph.stream(
            get_empty_state(messages=[HumanMessage(content=formatted_prompt)]),
            config,
            stream_mode="values",
        )

        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Response: {last_message.content}\n")

    except Exception as e:
        print(f"Error during prompt execution: {str(e)}")


@app.command()
def diagnostics(
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
    thread_id: str = typer.Option(
        None, "--thread-id", help="Resume conversation with this thread ID"
    ),
):
    """Diagnose issues with the setup"""
    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Generate or use provided thread ID
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            store.create_conversation(
                thread_id,
                "diagnostics",
                "Running diagnostics",
                model_name=resolved_model,
            )
        elif not store.conversation_exists(thread_id):
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        agent = create_configured_agent(model_name)
        try:
            run_prompt(run_diagnostic.content, agent, thread_id)
        finally:
            close_agent_resources(agent)

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


DEFAULT_PULSE_LIMIT = 50


@app.command()
def pulse(
    sort: Literal["created", "updated"] = typer.Option(
        "updated",
        "--sort",
        "-s",
        help="Sort starred repositories by: created or updated",
    ),
    direction: Literal["asc", "desc"] = typer.Option(
        "desc",
        "--direction",
        "-d",
        help="Sort direction: asc or desc",
    ),
    limit: int = typer.Option(
        DEFAULT_PULSE_LIMIT,
        "--limit",
        "-l",
        help="Maximum number of starred repositories to analyze (1-100)",
        min=1,
        max=100,
    ),
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
    thread_id: str = typer.Option(
        None, "--thread-id", help="Resume conversation with this thread ID"
    ),
):
    """Analyze activity of user's starred repositories"""
    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Build summary string with non-default parameters
        summary_parts = ["Analyzing starred repositories"]
        if sort != "updated":
            summary_parts.append(f"sort={sort}")
        if direction != "desc":
            summary_parts.append(f"direction={direction}")
        if limit != DEFAULT_PULSE_LIMIT:
            summary_parts.append(f"limit={limit}")
        summary = ", ".join(summary_parts)

        # Generate or use provided thread ID
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            store.create_conversation(
                thread_id,
                "pulse",
                summary,
                model_name=resolved_model,
            )
        elif not store.conversation_exists(thread_id):
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        agent = create_configured_agent(model_name)
        try:
            # Build filter descriptions for the prompt
            filter_descriptions = []
            if sort != "updated":
                filter_descriptions.append(f"- Sort by: {sort}")
            if direction != "desc":
                filter_descriptions.append(f"- Direction: {direction}")
            if limit != DEFAULT_PULSE_LIMIT:
                filter_descriptions.append(f"- Limit: {limit}")

            if filter_descriptions:
                filters_text = "\n".join(filter_descriptions)
            else:
                filters_text = "Using defaults (sort by recently updated, limit 50)"

            # Pass all parameters to template
            run_templated_prompt(
                starred_pulse,
                [sort, direction, str(limit), filters_text],
                agent,
                thread_id,
            )
        finally:
            close_agent_resources(agent)

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


DEFAULT_TOPIC_LIMIT = 25
DEFAULT_TOPIC_MIN_STARS = 25


@app.command()
def topics(
    topics_raw: str,
    sort: Literal["created", "updated"] = typer.Option(
        "updated",
        "--sort",
        "-s",
        help="Sort results by: stars, forks, or updated",
    ),
    limit: int = typer.Option(
        DEFAULT_TOPIC_LIMIT,
        "--limit",
        "-l",
        help="Maximum number of results to return (1-100)",
        min=1,
        max=100,
    ),
    language: str = typer.Option(
        None,
        "--language",
        help="Filter by programming language (e.g., 'python', 'rust')",
    ),
    license: str = typer.Option(
        None,
        "--license",
        help="Filter by license type (e.g., 'mit', 'apache-2.0', 'gpl-3.0')",
    ),
    min_stars: int = typer.Option(
        DEFAULT_TOPIC_MIN_STARS,
        "--min-stars",
        help="Minimum number of stars",
        min=0,
    ),
    max_stars: int = typer.Option(
        None,
        "--max-stars",
        help="Maximum number of stars",
        min=0,
    ),
    pushed_within_days: int = typer.Option(
        None,
        "--pushed-within-days",
        "-d",
        help="Only repos pushed within last N days (1-365)",
        min=1,
        max=365,
    ),
    archived: bool = typer.Option(
        None,
        "--archived",
        help="Filter by archived status (true=only archived, false=exclude archived)",
    ),
    fork: bool = typer.Option(
        None,
        "--fork",
        help="Filter by fork status (true=only forks, false=exclude forks)",
    ),
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
    thread_id: str = typer.Option(
        None, "--thread-id", help="Resume conversation with this thread ID"
    ),
):
    """Search for repositories related to specific topics/with specific labels"""
    from datetime import datetime, timedelta

    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Build summary string with non-default parameters
        summary_parts = [f"Searching topics: {topics_raw}"]
        if sort != "updated":
            summary_parts.append(f"sort={sort}")
        if limit != DEFAULT_TOPIC_LIMIT:
            summary_parts.append(f"limit={limit}")
        if language:
            summary_parts.append(f"language={language}")
        if license:
            summary_parts.append(f"license={license}")
        if min_stars != DEFAULT_TOPIC_MIN_STARS:
            summary_parts.append(f"min_stars={min_stars}")
        if max_stars:
            summary_parts.append(f"max_stars={max_stars}")
        if pushed_within_days:
            summary_parts.append(f"pushed_within_days={pushed_within_days}")
        if archived is not None:
            summary_parts.append(f"archived={archived}")
        if fork is not None:
            summary_parts.append(f"fork={fork}")
        summary = ", ".join(summary_parts)

        # Generate or use provided thread ID
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            store.create_conversation(
                thread_id,
                "topics",
                summary,
                model_name=resolved_model,
            )
        elif not store.conversation_exists(thread_id):
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        agent = create_configured_agent(model_name)
        try:
            parsed_topics = topics_raw.split(",")

            # Calculate absolute date from relative days if provided
            pushed_after = ""
            if pushed_within_days:
                date_threshold = datetime.now() - timedelta(days=pushed_within_days)
                pushed_after = date_threshold.strftime("%Y-%m-%d")

            # Build filter descriptions for the prompt
            filter_descriptions = []
            if language:
                filter_descriptions.append(f"- Language: {language}")
            if license:
                filter_descriptions.append(f"- License: {license}")
            if min_stars != DEFAULT_TOPIC_MIN_STARS or max_stars:
                if max_stars:
                    filter_descriptions.append(f"- Stars: {min_stars} to {max_stars}")
                else:
                    filter_descriptions.append(f"- Minimum stars: {min_stars}")
            if pushed_after:
                filter_descriptions.append(
                    f"- Pushed after: {pushed_after} "
                    f"(within last {pushed_within_days} days)"
                )
            if archived is not None:
                archived_text = "only archived" if archived else "exclude archived"
                filter_descriptions.append(f"- Archived: {archived_text}")
            if fork is not None:
                fork_text = "only forks" if fork else "exclude forks"
                filter_descriptions.append(f"- Fork status: {fork_text}")

            if filter_descriptions:
                filters_text = "\n".join(filter_descriptions)
            else:
                filters_text = "None"

            # Pass all parameters to template
            run_templated_prompt(
                topic_prompt,
                [
                    ", ".join(parsed_topics),
                    sort,
                    str(limit),
                    language or "",
                    license or "",
                    str(min_stars),
                    str(max_stars) if max_stars else "",
                    pushed_after,
                    str(archived).lower() if archived is not None else "",
                    str(fork).lower() if fork is not None else "",
                    filters_text,
                ],
                agent,
                thread_id,
            )
        finally:
            close_agent_resources(agent)

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


DEFAULT_DAYS = 90
DEFAULT_COMMITS = 200
DEFAULT_MIN_CHANGES = 3


@app.command()
def hotspots(
    repo: str,
    days: int = typer.Option(
        DEFAULT_DAYS,
        "--days",
        "-d",
        help="Number of days of history to analyze (1-365)",
        min=1,
        max=365,
    ),
    max_commits: int = typer.Option(
        DEFAULT_COMMITS,
        "--max-commits",
        "-c",
        help="Maximum number of commits to analyze (1-1000)",
        min=1,
        max=1000,
    ),
    min_changes: int = typer.Option(
        DEFAULT_MIN_CHANGES,
        "--min-changes",
        "-m",
        help="Minimum changes required for a file to be a hotspot (≥1)",
        min=1,
    ),
    path: str = typer.Option(
        None,
        "--path",
        "-p",
        help="Focus analysis on specific path (e.g., 'src/integrations')",
    ),
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
    thread_id: str = typer.Option(
        None, "--thread-id", help="Resume conversation with this thread ID"
    ),
    export_md: bool = typer.Option(
        False,
        "--export-md",
        help="Export analysis to markdown file in ./outputs/ directory",
    ),
):
    """Analyze maintenance hotspots in a repository"""
    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Build summary string with non-default parameters
        summary_parts = [f"Analyzing hotspots: {repo}"]
        if days != DEFAULT_DAYS:
            summary_parts.append(f"days={days}")
        if max_commits != DEFAULT_COMMITS:
            summary_parts.append(f"max_commits={max_commits}")
        if min_changes != DEFAULT_MIN_CHANGES:
            summary_parts.append(f"min_changes={min_changes}")
        if path:
            summary_parts.append(f"path={path}")
        summary = ", ".join(summary_parts)

        # Generate or use provided thread ID
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            store.create_conversation(
                thread_id,
                "hotspots",
                summary,
                model_name=resolved_model,
            )
        elif not store.conversation_exists(thread_id):
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        agent = create_configured_agent(model_name)
        try:
            # Build path instruction
            path_instruction = (
                f"- Focus analysis on the path: {path}"
                if path
                else "- Analyze all files in the repository"
            )

            # Pass all parameters to template
            run_templated_prompt(
                hotspot_analysis,
                [repo, str(days), str(max_commits), str(min_changes), path_instruction],
                agent,
                thread_id,
            )
        finally:
            close_agent_resources(agent)

        # Export to markdown if requested
        if export_md:
            try:
                from export.writer import (
                    export_hotspot_analysis,
                )

                filepath = export_hotspot_analysis(
                    store=store,
                    thread_id=thread_id,
                    repo=repo,
                    days=days,
                    max_commits=max_commits,
                    min_changes=min_changes,
                    path_filter=path,
                    strategy="activity",  # TODO: extract from params if configurable
                )
                print(f"\n📄 Analysis exported to: {filepath}")
            except Exception as e:
                print(f"\n⚠️  Export failed: {str(e)}")

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


@app.command()
def history(
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of conversations to show"
    ),
):
    """List recent conversation history"""
    with ConversationStore() as store:
        conversations = store.list_conversations(limit)

        if not conversations:
            print("No conversation history found.")
            return

        print(f"\n📚 Recent Conversations (showing up to {limit}):\n")

        for conv in conversations:
            created = conv["created_at"][:19]  # Trim microseconds
            updated = conv["updated_at"][:19]
            msg_count = conv["message_count"]

            print(f"🔹 Thread ID: {conv['thread_id']}")
            print(f"   Command:   {conv['command']}")
            if conv["model_name"]:
                print(f"   Model:     {conv['model_name']}")
            if conv["summary"]:
                print(f"   Summary:   {conv['summary']}")
            print(f"   Created:   {created}")
            print(f"   Updated:   {updated}")
            print(f"   Messages:  {msg_count}")
            print()


@app.command()
def show(thread_id: str):
    """Display full conversation transcript"""
    with ConversationStore() as store:
        conversation = store.get_conversation(thread_id)

        if conversation is None:
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        print(f"\n📖 Conversation: {thread_id}")
        print(f"Command: {conversation['command']}")
        if conversation["model_name"]:
            print(f"Model: {conversation['model_name']}")
        if conversation["summary"]:
            print(f"Summary: {conversation['summary']}")
        print(f"Created: {conversation['created_at'][:19]}")
        print(f"Updated: {conversation['updated_at'][:19]}")
        print(f"\n{'=' * 70}\n")

        for i, msg in enumerate(conversation["messages"], 1):
            role = msg["role"].upper()
            timestamp = msg["created_at"][:19]

            print(f"[{i}] {role} ({timestamp}):")
            print(msg["content"])
            print(f"\n{'-' * 70}\n")


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


@app.command()
def chat(
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Start a new interactive chat session"""
    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Generate new thread ID
        thread_id = str(uuid.uuid4())
        store.create_conversation(
            thread_id, "chat", "Interactive chat session", model_name=resolved_model
        )

        print(f"\n💬 Starting new chat session: {thread_id}")
        print(f"Model: {resolved_model}\n")

        # Create graph with the specified model
        agent = create_configured_agent(model_name)
        try:
            # Run interactive session
            run_interactive_session(agent, thread_id)
        finally:
            close_agent_resources(agent)

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


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


@app.command()
def resume(
    thread_id: str = typer.Argument(
        None, help="Thread ID to resume (omit to use --last)"
    ),
    last: bool = typer.Option(
        False, "--last", help="Resume the most recent conversation"
    ),
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Resume an existing conversation interactively"""
    try:
        resume_conversation(thread_id=thread_id, last=last, model_name=model_name)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except LookupError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def ui(
    share: bool = typer.Option(False, "--share", help="Create a public share link"),
    server_name: str = typer.Option(
        "127.0.0.1", "--host", help="Server hostname/IP address"
    ),
    server_port: int = typer.Option(7860, "--port", help="Server port number"),
):
    """Launch the Gradio web UI"""
    from ui import launch_ui

    print(f"\n🚀 Launching Gradio UI on http://{server_name}:{server_port}")
    launch_ui(share=share, server_name=server_name, server_port=server_port)


if __name__ == "__main__":
    app()
