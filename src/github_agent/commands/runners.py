from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from core.models import TemplatedPrompt
from integrations.github.agent import close_agent_resources, create_configured_agent
from integrations.github.models import GitHubToolState, get_empty_state
from storage import ConversationStore


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
    "run_prompt",
    "run_templated_prompt",
    "run_interactive_session",
    "resume_conversation",
]
