"""Conversation history REST endpoints, backed by ConversationStore."""

from fastapi import APIRouter, HTTPException

from api.schemas import ConversationDetail, ConversationSummary, MessageOut, coerce_text
from storage import ConversationStore

router = APIRouter()


@router.get("/conversations")
def list_conversations(limit: int = 20) -> list[ConversationSummary]:
    """List recent conversations with message counts."""
    with ConversationStore() as store:
        return [
            ConversationSummary(
                thread_id=conv["thread_id"],
                command=conv["command"],
                model_name=conv.get("model_name"),
                summary=conv.get("summary"),
                created_at=conv["created_at"],
                updated_at=conv["updated_at"],
                message_count=conv["message_count"],
            )
            for conv in store.list_conversations(limit=limit)
        ]


@router.get("/conversations/{thread_id}")
def get_conversation(thread_id: str) -> ConversationDetail:
    """Return a single conversation with its full message history."""
    with ConversationStore() as store:
        conversation = store.get_conversation(thread_id)

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        MessageOut(
            role=msg["role"],
            content=coerce_text(msg["content"]),
            created_at=msg.get("created_at", ""),
        )
        for msg in conversation["messages"]
    ]
    return ConversationDetail(
        thread_id=conversation["thread_id"],
        command=conversation["command"],
        model_name=conversation.get("model_name"),
        summary=conversation.get("summary"),
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
        messages=messages,
    )
