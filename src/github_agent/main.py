import uuid
from typing import cast

import typer
from dotenv import load_dotenv

from core.config import get_config
from core.llm import is_ai_message
from core.models import TemplatedPrompt, ThreadedPrompt
from core.prompts import comprehensive_analysis, run_diagnostic, topic_prompt
from integrations.github.agent import create_graph
from storage import ConversationStore

# Load environment variables
load_dotenv()

app = typer.Typer(rich_markup_mode="rich")


def get_resolved_model_name(model_name_override: str | None = None) -> str:
    """Get the actual model name that will be used.

    Args:
        model_name_override: CLI-provided model name that overrides settings.

    Returns:
        The resolved model name
    """
    if model_name_override is not None:
        provider_config = get_config(model_name=model_name_override)
    else:
        provider_config = get_config()

    # Return the same defaults as create_llm
    return provider_config.get_model_or_default()


def create_configured_graph(model_name_override: str | None = None):
    """Create a graph with the specified model configuration.

    Args:
        model_name_override: CLI-provided model name that overrides settings.

    Returns:
        Configured LangGraph instance
    """
    if model_name_override is not None:
        provider_config = get_config(model_name=model_name_override)
    else:
        provider_config = get_config()

    return create_graph(
        provider_config,
    )


def run_prompt(prompt: ThreadedPrompt, graph, thread_id: str, store: ConversationStore):
    # Configure thread
    config = {"configurable": {"thread_id": thread_id}}

    # Run the analysis
    try:
        # Initialize with our first message
        events = graph.stream(
            {"messages": [("user", prompt.prompt)]}, config, stream_mode="values"
        )

        # Store the user message
        store.add_message(thread_id, "user", prompt.prompt)

        # Track if we hit a stop condition
        should_stop = False
        stop_reason = None

        # Print each event as it occurs
        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Step output: {last_message.content}\n")

                # Store assistant messages
                if is_ai_message(last_message):
                    store.add_message(
                        thread_id, "assistant", cast(str, last_message.content)
                    )

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
            # Store follow-up question
            store.add_message(thread_id, "user", follow_up)

            events = graph.stream(
                {"messages": [("user", follow_up)]}, config, stream_mode="values"
            )

            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]

                    # Store assistant responses
                    if is_ai_message(last_message):
                        store.add_message(
                            thread_id, "assistant", cast(str, last_message.content)
                        )

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
    store: ConversationStore,
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

    # Store the user message
    store.add_message(thread_id, "user", formatted_prompt)

    # Run the formatted prompt through the graph
    try:
        events = graph.stream(
            {"messages": [("user", formatted_prompt)]}, config, stream_mode="values"
        )

        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]

                # Store assistant messages
                if is_ai_message(last_message):
                    store.add_message(
                        thread_id, "assistant", cast(str, last_message.content)
                    )

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
    store = ConversationStore()

    # Get the resolved model name
    resolved_model = get_resolved_model_name(model_name)

    # Generate or use provided thread ID
    if thread_id is None:
        thread_id = str(uuid.uuid4())
        store.create_conversation(
            thread_id, "diagnostics", "Running diagnostics", model_name=resolved_model
        )
    elif not store.conversation_exists(thread_id):
        typer.echo(f"Error: Conversation {thread_id} not found", err=True)
        raise typer.Exit(1)

    graph = create_configured_graph(model_name)
    run_prompt(run_diagnostic, graph, thread_id, store)

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
    store = ConversationStore()

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

    graph = create_configured_graph(model_name)
    run_prompt(comprehensive_analysis, graph, thread_id, store)

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
    store = ConversationStore()

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

    graph = create_configured_graph(model_name)
    parsed_topics = topics_raw.split(",")

    run_templated_prompt(topic_prompt, parsed_topics, graph, thread_id, store)

    print(f"\n💾 Conversation saved with thread ID: {thread_id}")


@app.command()
def history(
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of conversations to show"
    ),
):
    """List recent conversation history"""
    store = ConversationStore()
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
    store = ConversationStore()
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


@app.command()
def resume(
    thread_id: str,
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Resume an existing conversation interactively"""
    store = ConversationStore()

    # Verify conversation exists
    if not store.conversation_exists(thread_id):
        typer.echo(f"Error: Conversation {thread_id} not found", err=True)
        raise typer.Exit(1)

    # Show conversation summary
    conversation = store.get_conversation(thread_id)
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
    graph = create_configured_graph(model_name)
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

            # Store user message
            store.add_message(thread_id, "user", user_input)

            # Stream response
            events = graph.stream(
                {"messages": [("user", user_input)]}, config, stream_mode="values"
            )

            print("\nAssistant: ", end="", flush=True)
            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]
                    if hasattr(last_message, "content"):
                        # Store assistant response
                        if is_ai_message(last_message):
                            store.add_message(
                                thread_id, "assistant", cast(str, last_message.content)
                            )

                        print(last_message.content)

            print()  # New line after response

        except KeyboardInterrupt:
            print("\n\n👋 Ending conversation.")
            break
        except EOFError:
            print("\n👋 Ending conversation.")
            break


if __name__ == "__main__":
    app()
