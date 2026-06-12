"""Pydantic request/response models for the HTTP API.

These models are the single source of truth for the API contract: the frontend
TypeScript types are generated from the OpenAPI schema FastAPI derives from them
(`pnpm gen:api`), so keep them well-typed and descriptive.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from storage.favorites import SavedRepository


def coerce_text(content: Any) -> str:
    """Flatten LangChain message content into plain text.

    Content may be a ``str`` (Ollama/HuggingFace) or a list of blocks (Anthropic
    returns ``[{"type": "text", "text": "..."}, ...]``).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, Mapping) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content) if content is not None else ""


class MessageOut(BaseModel):
    """A single conversation message."""

    role: str
    content: str
    created_at: str = ""


class ConversationSummary(BaseModel):
    """Conversation metadata plus a message count (list view)."""

    thread_id: str
    command: str
    model_name: str | None = None
    summary: str | None = None
    created_at: str
    updated_at: str
    message_count: int


class ConversationDetail(BaseModel):
    """Full conversation: metadata plus its messages."""

    thread_id: str
    command: str
    model_name: str | None = None
    summary: str | None = None
    created_at: str
    updated_at: str
    messages: list[MessageOut] = Field(default_factory=list)


class ConfigOut(BaseModel):
    """Runtime configuration the SPA needs (no secrets)."""

    provider: str
    model_name: str
    languages: list[str]


class SavedRepositoryIn(BaseModel):
    """Payload for saving a repository to favorites."""

    full_name: str = Field(..., description="e.g., 'owner/repo'")
    url: str
    stars: int = 0
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    description: str = ""


class FavoritesOut(BaseModel):
    """The current set of saved repositories."""

    saved_repos: list[SavedRepository] = Field(default_factory=list)
