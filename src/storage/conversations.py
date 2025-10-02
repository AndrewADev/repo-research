"""Conversation metadata storage using SQLite.

Note: Message persistence is handled by LangGraph's SqliteSaver.
This class only manages conversation metadata (command, model, summary, timestamps).
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver


class ConversationStore:
    """Manages conversation metadata persistence using SQLite.

    Message content is stored and retrieved via LangGraph's SqliteSaver checkpoints.
    This class handles conversation-level metadata like command, model, summary, etc.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize conversation metadata store.

        Args:
            db_path: Path to SQLite database.
                Defaults to ~/.github-agent/conversations.db
                Note: This should be the same database used by SqliteSaver.
        """
        if db_path is None:
            home_dir = Path.home()
            storage_dir = home_dir / ".github-agent"
            storage_dir.mkdir(exist_ok=True)
            db_path = str(storage_dir / "conversations.db")

        self.db_path = db_path
        self._init_db()

        # Create checkpointer for reading messages from LangGraph checkpoints
        self._checkpoint_conn = sqlite3.connect(db_path, check_same_thread=False)
        self._checkpointer = SqliteSaver(self._checkpoint_conn)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connections."""
        self.close()
        return False

    def close(self):
        """Close database connections."""
        if hasattr(self, "_checkpoint_conn"):
            self._checkpoint_conn.close()

    def _get_connection(self):
        """Get a database connection.

        Note: Caller is responsible for closing the connection.
        """
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database schema for conversation metadata.

        Note: LangGraph's SqliteSaver creates its own tables for checkpoint storage.
        We only manage conversation-level metadata here.
        """
        conn = self._get_connection()
        try:
            # Create metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT UNIQUE NOT NULL,
                    command TEXT NOT NULL,
                    model_name TEXT,
                    summary TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_metadata_thread_id
                ON conversation_metadata(thread_id)
            """)

            conn.commit()
        finally:
            conn.close()

    def create_conversation(
        self,
        thread_id: str,
        command: str,
        summary: str | None = None,
        model_name: str | None = None,
    ) -> int:
        """Create a new conversation metadata record.

        Args:
            thread_id: Unique thread identifier (used by LangGraph checkpointer)
            command: Command that started the conversation
            summary: Optional summary of the conversation
            model_name: Optional model name used for this conversation

        Returns:
            Metadata record ID
        """
        now = datetime.now(UTC).isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO conversation_metadata
                (thread_id, command, model_name, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (thread_id, command, model_name, summary, now, now),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_conversation(self, thread_id: str) -> dict[str, Any] | None:
        """Get conversation metadata with messages from LangGraph checkpoints.

        Args:
            thread_id: Thread identifier

        Returns:
            Dictionary with conversation metadata and messages, or None if not found
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row

            # Get conversation metadata
            cursor = conn.execute(
                """
                SELECT
                    id, thread_id, command, model_name, summary,
                    created_at, updated_at
                FROM conversation_metadata
                WHERE thread_id = ?
            """,
                (thread_id,),
            )
            conv_row = cursor.fetchone()

            if conv_row is None:
                return None

            conversation = dict(conv_row)

            # Get messages from LangGraph checkpoints
            messages = self.get_messages_from_checkpoints(thread_id)
            conversation["messages"] = messages

            return conversation
        finally:
            conn.close()

    def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent conversations with message counts from checkpoints.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of conversation summaries with metadata
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                """
                SELECT
                    thread_id,
                    command,
                    model_name,
                    summary,
                    created_at,
                    updated_at
                FROM conversation_metadata
                ORDER BY updated_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            conversations = []
            for row in cursor.fetchall():
                conv = dict(row)
                # Get message count from checkpoints
                messages = self.get_messages_from_checkpoints(conv["thread_id"])
                conv["message_count"] = len(messages)
                conversations.append(conv)

            return conversations
        finally:
            conn.close()

    def get_most_recent_conversation(self) -> dict[str, Any] | None:
        """Get the most recently updated conversation metadata.

        Returns:
            Dictionary with conversation metadata, or None if no conversations exist
        """
        conversations = self.list_conversations(limit=1)
        return conversations[0] if conversations else None

    def update_summary(self, thread_id: str, summary: str):
        """Update conversation summary in metadata.

        Args:
            thread_id: Thread identifier
            summary: New summary text
        """
        now = datetime.now(UTC).isoformat()

        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE conversation_metadata
                SET summary = ?, updated_at = ?
                WHERE thread_id = ?
            """,
                (summary, now, thread_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_conversation(self, thread_id: str) -> bool:
        """Delete a conversation's metadata.

        Note: LangGraph checkpoints are not deleted; only metadata is removed.

        Args:
            thread_id: Thread identifier

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id FROM conversation_metadata WHERE thread_id = ?", (thread_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return False

            # Delete metadata record
            conn.execute(
                "DELETE FROM conversation_metadata WHERE thread_id = ?", (thread_id,)
            )

            conn.commit()
            return True
        finally:
            conn.close()

    def conversation_exists(self, thread_id: str) -> bool:
        """Check if a conversation metadata record exists.

        Args:
            thread_id: Thread identifier

        Returns:
            True if conversation metadata exists
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM conversation_metadata WHERE thread_id = ? LIMIT 1",
                (thread_id,),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_messages_from_checkpoints(self, thread_id: str) -> list[dict[str, Any]]:
        """Extract messages from LangGraph checkpoints for a conversation.

        Args:
            thread_id: Thread identifier

        Returns:
            List of message dictionaries with role, content, and created_at fields
        """
        messages = []
        config = {"configurable": {"thread_id": thread_id}}

        try:
            # Get all checkpoints for this thread
            checkpoints = list(self._checkpointer.list(config))

            if not checkpoints:
                return messages

            # Get the most recent checkpoint (first in list)
            latest_checkpoint = checkpoints[0]

            # Extract messages from checkpoint state
            checkpoint_value = latest_checkpoint.checkpoint
            if checkpoint_value and "channel_values" in checkpoint_value:
                channel_values = checkpoint_value["channel_values"]
                if "messages" in channel_values:
                    for msg in channel_values["messages"]:
                        # Convert LangChain message to dict format
                        role = (
                            "user"
                            if hasattr(msg, "type") and msg.type == "human"
                            else "assistant"
                        )
                        content = msg.content if hasattr(msg, "content") else str(msg)

                        messages.append(
                            {
                                "role": role,
                                "content": content,
                                "created_at": latest_checkpoint.metadata.get(
                                    "created_at", ""
                                ),
                            }
                        )

        except Exception:
            # If checkpoints don't exist or can't be read, return empty list
            pass

        return messages
