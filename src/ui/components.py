"""Reusable Gradio UI components for Repo Research."""

import gradio as gr

from storage import ConversationStore


def render_conversation(conversation: dict) -> str:
    """Render conversation messages as formatted HTML with markdown content.

    Args:
        conversation: Conversation dictionary with messages

    Returns:
        HTML string with formatted conversation
    """
    if not conversation or "messages" not in conversation:
        return "<p>No messages found.</p>"

    import markdown

    html_parts = ['<div style="font-family: sans-serif; line-height: 1.6;">']

    # Header with metadata
    html_parts.append(
        '<div style="margin-bottom: 20px; padding: 15px; background: #f5f5f5; '
        'border-radius: 8px; color: #000;">'
    )
    html_parts.append(f"<strong>Thread ID:</strong> {conversation['thread_id']}<br>")
    html_parts.append(f"<strong>Command:</strong> {conversation['command']}<br>")
    if conversation.get("model_name"):
        html_parts.append(f"<strong>Model:</strong> {conversation['model_name']}<br>")
    if conversation.get("summary"):
        html_parts.append(f"<strong>Summary:</strong> {conversation['summary']}<br>")
    html_parts.append(
        f"<strong>Created:</strong> {conversation['created_at'][:19]}<br>"
    )
    html_parts.append(f"<strong>Messages:</strong> {len(conversation['messages'])}")
    html_parts.append("</div>")

    # Messages - render markdown content as HTML with colored backgrounds
    for i, msg in enumerate(conversation["messages"], 1):
        role = msg["role"]
        content = msg["content"]

        # Format based on role with colored backgrounds
        if role == "user":
            role_label = "👤 User"
            bg_color = "#e3f2fd"
            border_color = "#2196F3"
        else:
            role_label = "🤖 Assistant"
            bg_color = "#f1f8e9"
            border_color = "#8BC34A"

        # Convert markdown content to HTML with table support
        content_html = markdown.markdown(
            content, extensions=["tables", "fenced_code", "nl2br", "codehilite"]
        )

        # Create styled div with HTML content
        # Use explicit concatenation to avoid f-string issues with curly braces
        # Add strong color styling to override Gradio's dark theme
        message_html = (
            f'<div style="margin: 10px 0; padding: 15px; background: {bg_color}; '
            f"border-radius: 8px; border-left: 4px solid {border_color}; "
            f'color: #000 !important;">'
            f'<strong style="color: #000 !important;">[{i}] {role_label}</strong>'
            "<br><br>"
            f'<div style="color: #000 !important;">{content_html}</div>'
            "</div>"
        )
        html_parts.append(message_html)

    html_parts.append("</div>")  # Close wrapper div
    return "\n".join(html_parts)


def render_conversation_list(conversations: list[dict]) -> list:
    """Render conversation list as table data.

    Args:
        conversations: List of conversation summaries

    Returns:
        List of lists for Gradio DataFrame
    """
    if not conversations:
        return []

    table_data = []
    for conv in conversations:
        row = [
            conv["thread_id"],
            conv["command"],
            conv.get("summary", ""),
            conv.get("model_name", ""),
            conv["created_at"][:19],
            conv["message_count"],
        ]
        table_data.append(row)

    return table_data


def load_conversation_details(thread_id: str | None, evt: gr.SelectData) -> str:
    """Load full conversation details when row is selected.

    Args:
        thread_id: Current thread ID (unused, for Gradio state)
        evt: Gradio SelectData event with row index

    Returns:
        HTML formatted conversation
    """
    if evt is None or evt.index is None:
        return "<p>No conversation selected.</p>"

    # Extract thread_id from selected row (first column)
    row_index = evt.index[0]

    with ConversationStore() as store:
        conversations = store.list_conversations(limit=100)
        if row_index >= len(conversations):
            return "<p>Invalid conversation selection.</p>"

        selected_thread_id = conversations[row_index]["thread_id"]
        conversation = store.get_conversation(selected_thread_id)

        if conversation is None:
            return "<p>Conversation not found.</p>"

        return render_conversation(conversation)


def get_conversation_history(limit: int = 20) -> list:
    """Fetch conversation history from storage.

    Args:
        limit: Maximum number of conversations to retrieve

    Returns:
        Table data for Gradio DataFrame
    """
    with ConversationStore() as store:
        conversations = store.list_conversations(limit=limit)
        return render_conversation_list(conversations)
