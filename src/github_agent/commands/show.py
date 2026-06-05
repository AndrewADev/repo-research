import typer

from storage import ConversationStore


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


def register(app: typer.Typer) -> None:
    app.command()(show)
