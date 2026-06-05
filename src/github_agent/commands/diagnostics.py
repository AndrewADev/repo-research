import uuid

import typer

from core.config import get_resolved_model_name
from core.prompts import run_diagnostic
from integrations.github.agent import close_agent_resources, create_configured_agent
from storage import ConversationStore

from .runners import run_prompt


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


def register(app: typer.Typer) -> None:
    app.command()(diagnostics)
