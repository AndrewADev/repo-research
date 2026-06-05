import uuid
from typing import Literal

import typer

from core.config import get_resolved_model_name
from core.prompts import topic_prompt
from integrations.github.agent import close_agent_resources, create_configured_agent
from storage import ConversationStore

from .runners import run_templated_prompt

DEFAULT_TOPIC_LIMIT = 25
DEFAULT_TOPIC_MIN_STARS = 25


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


def register(app: typer.Typer) -> None:
    app.command()(topics)
