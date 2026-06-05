import typer

from storage import ConversationStore


def history(
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of conversations to show"
    ),
):
    """List recent conversation history"""
    with ConversationStore() as store:
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


def register(app: typer.Typer) -> None:
    app.command()(history)
