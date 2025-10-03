import uuid

import typer
from dotenv import load_dotenv
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from core.config import get_config, get_resolved_model_name
from core.models import TemplatedPrompt, ThreadedPrompt
from core.prompts import comprehensive_analysis, run_diagnostic, topic_prompt
from integrations.github.agent import create_graph
from storage import ConversationStore

# Load environment variables
load_dotenv()

app = typer.Typer(rich_markup_mode="rich")


def create_configured_agent(
    model_name_override: str | None = None, memory: BaseCheckpointSaver | None = None
):
    """Create a graph with the specified model configuration.

    Args:
        model_name_override: CLI-provided model name that overrides settings.

    Returns:
        Tuple of graph - caller must close connection
    """
    if model_name_override is not None:
        provider_config = get_config(model_name=model_name_override)
    else:
        provider_config = get_config()

    return create_graph(
        provider_config,
        memory,
    )


def close_agent_resources(graph: CompiledStateGraph):
    """Close checkpointer database connection if present."""
    if isinstance(graph.checkpointer, SqliteSaver):
        if hasattr(graph.checkpointer.conn, "close") and callable(
            graph.checkpointer.conn.close
        ):
            graph.checkpointer.conn.close()


def run_prompt(prompt: ThreadedPrompt, graph, thread_id: str):
    # Configure thread
    config = {"configurable": {"thread_id": thread_id}}

    # Run the analysis
    try:
        # Initialize with our first message
        # LangGraph's SqliteSaver will automatically persist all messages
        events = graph.stream(
            {"messages": [("user", prompt.prompt)]}, config, stream_mode="values"
        )

        # Track if we hit a stop condition
        should_stop = False
        stop_reason = None

        # Print each event as it occurs
        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Step output: {last_message.content}\n")

                # Check for various stop conditions
                if hasattr(last_message, "content"):
                    content = last_message.content
                    if "Execution Stopped Due to Diagnostics" in content:
                        should_stop = True
                        stop_reason = "diagnostics"
                    elif "Task Concluded" in content:
                        should_stop = True
                        stop_reason = "no_results"

    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        should_stop = True
        stop_reason = "exception"

    # Only run follow-ups if we didn't stop
    if not should_stop:
        for follow_up in prompt.follow_ups:
            # Messages automatically persisted by SqliteSaver
            events = graph.stream(
                {"messages": [("user", follow_up)]}, config, stream_mode="values"
            )

            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]
                    print(f"Follow-up response: {last_message.content}\n")

    else:
        if stop_reason == "diagnostics":
            print("⚠️ Skipping follow-up prompts due to diagnostic stop condition.")
        elif stop_reason == "no_results":
            print("✅ Task completed - no results found.")
        elif stop_reason == "exception":
            print("❌ Skipping follow-up prompts due to error.")


def run_templated_prompt(
    prompt: TemplatedPrompt,
    user_args: list[str],
    graph,
    thread_id: str,
):
    # Configure thread
    config = {"configurable": {"thread_id": thread_id}}

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

    # Run the formatted prompt through the graph
    # LangGraph's SqliteSaver will automatically persist all messages
    try:
        events = graph.stream(
            {"messages": [("user", formatted_prompt)]}, config, stream_mode="values"
        )

        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Response: {last_message.content}\n")

    except Exception as e:
        print(f"Error during templated prompt execution: {str(e)}")


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
            run_prompt(run_diagnostic, agent, thread_id)
        finally:
            close_agent_resources(agent)

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


@app.command()
def analyze(
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
    thread_id: str = typer.Option(
        None, "--thread-id", help="Resume conversation with this thread ID"
    ),
):
    """Run comprehensive analysis of starred repositories"""
    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Generate or use provided thread ID
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            store.create_conversation(
                thread_id,
                "analyze",
                "Analyzing starred repositories",
                model_name=resolved_model,
            )
        elif not store.conversation_exists(thread_id):
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        agent = create_configured_agent(model_name)
        try:
            run_prompt(comprehensive_analysis, agent, thread_id)
        finally:
            close_agent_resources(agent)

        print(f"\n💾 Conversation saved with thread ID: {thread_id}")


@app.command()
def topics(
    topics_raw: str,
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
    thread_id: str = typer.Option(
        None, "--thread-id", help="Resume conversation with this thread ID"
    ),
):
    """Search for repositories related to specific topics/with specific labels"""
    # Initialize storage
    with ConversationStore() as store:
        # Get the resolved model name
        resolved_model = get_resolved_model_name(model_name)

        # Generate or use provided thread ID
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            store.create_conversation(
                thread_id,
                "topics",
                f"Searching topics: {topics_raw}",
                model_name=resolved_model,
            )
        elif not store.conversation_exists(thread_id):
            typer.echo(f"Error: Conversation {thread_id} not found", err=True)
            raise typer.Exit(1)

        agent = create_configured_agent(model_name)
        try:
            parsed_topics = topics_raw.split(",")
            run_templated_prompt(topic_prompt, parsed_topics, agent, thread_id)
        finally:
            close_agent_resources(agent)

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


def run_interactive_session(graph, thread_id: str):
    """Run an interactive chat session.

    Args:
        graph: Configured LangGraph instance
        thread_id: Thread identifier for the conversation
        store: ConversationStore instance (for metadata only)
    """
    config = {"configurable": {"thread_id": thread_id}}

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
                {"messages": [("user", user_input)]}, config, stream_mode="values"
            )

            print("\nAssistant: ", end="", flush=True)
            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]
                    if hasattr(last_message, "content"):
                        print(last_message.content)

            print()  # New line after response

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
