"""Writes hotspot analysis results to markdown format.

Handles extraction of conversation data and hotspot results from storage,
then delegates to markdown module functions for file generation.
"""

from datetime import datetime
from typing import cast

from langchain_core.messages import AIMessage

from storage import ConversationStore

from .formats import markdown as md
from .models import ExportMetadata


def export_hotspot_analysis(
    store: ConversationStore,
    thread_id: str,
    repo: str,
    days: int,
    max_commits: int,
    min_changes: int,
    path_filter: str | None,
    strategy: str = "activity",
) -> str:
    """Export hotspot analysis to markdown file.

    Args:
        store: ConversationStore instance
        thread_id: Thread ID of the conversation
        repo: Repository name
        days: Number of days analyzed
        max_commits: Maximum commits analyzed
        min_changes: Minimum changes threshold
        path_filter: Optional path filter
        strategy: Churn calculation strategy used

    Returns:
        Path to the exported file

    Raises:
        ValueError: If conversation cannot be retrieved
    """
    # Get conversation from store
    conversation = store.get_conversation(thread_id)
    if conversation is None:
        raise ValueError(f"Could not retrieve conversation {thread_id}")

    if not conversation["messages"] or len(conversation["messages"]) < 1:
        raise ValueError("No messages found to export")

    # Sanity check: verify last message looks like a hotspot analysis
    has_hotspot_analysis = False
    last_message = None

    # TODO: Likely we can improve/simplify the following checks with
    #   LangChain v1 (additional metadata and props on messages)
    for msg in reversed(conversation["messages"]):
        if msg.get("role") == "assistant":
            last_message = msg
            # Extract content from either dict or LangChain message
            content_str = msg["content"] if isinstance(msg, dict) else msg.content
            content = cast(str, content_str).lower()
            # Check for indicators of hotspot analysis
            has_table = "|" in content and "---" in content
            has_hotspot_keywords = any(
                keyword in content
                for keyword in [
                    "hotspot",
                    "churn",
                    "maintenance",
                    "changes",
                    "additions",
                    "deletions",
                ]
            )
            has_hotspot_analysis = has_table and has_hotspot_keywords
            break

    # Log if we didn't detect hotspot analysis patterns
    if not has_hotspot_analysis:
        print(
            "⚠️  Last message doesn't appear to contain hotspot analysis. "
            "Exporting conversation anyway."
        )

    # Generate export metadata
    # Use timestamp from last message if available, otherwise current time
    analysis_date = datetime.now()
    if last_message and "created_at" in last_message and last_message["created_at"]:
        analysis_date = datetime.fromisoformat(last_message["created_at"])

    metadata = ExportMetadata(
        repo_name=repo,
        analysis_date=analysis_date,
        # It is not currently easy to get commit SHA reliably without more
        # metadata in the messages, so it is None here
        # TODO: Include it (directly or via reference) in the metadata/extra
        # props once migrated to LC v1
        latest_commit_sha=None,
    )

    # Generate markdown report
    markdown_content = md.generate_markdown_report(
        metadata=metadata,
        analysis_message=AIMessage(content=cast(dict, last_message)["content"]),
        strategy=strategy,
        days=days,
        max_commits=max_commits,
        min_changes=min_changes,
        path_filter=path_filter,
    )

    # Export to file
    md.write_to_file(markdown_content, metadata.filepath)

    return str(metadata.filepath)
