"""Checkpoint serializer wired with this project's state types.

LangGraph's default msgpack serializer warns (and will eventually block) on
any unregistered type it finds in a checkpoint. Our `GitHubToolState` stores
custom Pydantic models that have to be allowlisted explicitly.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from integrations.github.models import RepositoryRecord

# Custom Pydantic models that appear in `GitHubToolState` and therefore land
# in LangGraph checkpoints. Extend this when adding new state-resident types.
_ALLOWED_CHECKPOINT_TYPES: tuple[type, ...] = (RepositoryRecord,)


def make_checkpoint_serde() -> JsonPlusSerializer:
    """Build a JsonPlusSerializer that recognises our state Pydantic models."""
    return JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_CHECKPOINT_TYPES)


def make_sync_sqlite_saver(conn) -> SqliteSaver:
    """Build a SqliteSaver wired to our checkpoint serde."""
    return SqliteSaver(conn, serde=make_checkpoint_serde())


@asynccontextmanager
async def open_async_sqlite_saver(db_path: str) -> AsyncIterator[AsyncSqliteSaver]:
    """Replace `AsyncSqliteSaver.from_conn_string` so we can inject our serde."""
    async with aiosqlite.connect(db_path) as conn:
        yield AsyncSqliteSaver(conn, serde=make_checkpoint_serde())
