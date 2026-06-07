import uuid

import typer

from core.config import get_resolved_model_name
from integrations.github.agent import close_agent_resources, create_configured_agent
from storage import ConversationStore

from .runners import run_interactive_session


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


def register(app: typer.Typer) -> None:
    app.command()(chat)
