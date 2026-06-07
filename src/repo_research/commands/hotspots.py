import uuid

import typer

from core.config import get_resolved_model_name
from core.prompts import hotspot_analysis
from integrations.github.agent import close_agent_resources, create_configured_agent
from storage import ConversationStore

from .runners import run_templated_prompt

DEFAULT_DAYS = 90
DEFAULT_COMMITS = 200
DEFAULT_MIN_CHANGES = 3


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


def register(app: typer.Typer) -> None:
    app.command()(hotspots)
