import uuid
from typing import Literal

import typer

from core.config import get_resolved_model_name
from core.prompts import starred_pulse
from integrations.github.agent import close_agent_resources, create_configured_agent
from storage import ConversationStore

from .runners import run_templated_prompt

DEFAULT_PULSE_LIMIT = 50


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


def register(app: typer.Typer) -> None:
    app.command()(pulse)
