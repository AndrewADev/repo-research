"""Conversation storage using SQLite."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ConversationStore:
    """Manages conversation persistence using SQLite."""

    def __init__(self, db_path: str | None = None):
        """Initialize conversation store.

        Args:
            db_path: Path to SQLite database.
                Defaults to ~/.github-agent/conversations.db
        """
        if db_path is None:
            home_dir = Path.home()
            storage_dir = home_dir / ".github-agent"
            storage_dir.mkdir(exist_ok=True)
            db_path = str(storage_dir / "conversations.db")

        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Get a database connection.

        Note: Caller is responsible for closing the connection.
        """
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
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
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_thread_id
                ON conversations(thread_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                ON messages(conversation_id)
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
        """Create a new conversation.

        Args:
            thread_id: Unique thread identifier
            command: Command that started the conversation
            summary: Optional summary of the conversation
            model_name: Optional model name used for this conversation

        Returns:
            Conversation ID
        """
        now = datetime.now(UTC).isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO conversations
                (thread_id, command, model_name, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (thread_id, command, model_name, summary, now, now),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a message to a conversation.

        Args:
            thread_id: Thread identifier
            role: Message role (user, assistant, system, etc.)
            content: Message content
            metadata: Optional metadata dictionary
        """
        now = datetime.now(UTC).isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        conn = self._get_connection()
        try:
            # Get conversation ID
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE thread_id = ?", (thread_id,)
            )
            row = cursor.fetchone()

            if row is None:
                raise ValueError(f"Conversation with thread_id {thread_id} not found")

            conversation_id = row[0]

            # Insert message
            conn.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (conversation_id, role, content, metadata_json, now),
            )

            # Update conversation timestamp
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

            conn.commit()
        finally:
            conn.close()

    def get_conversation(self, thread_id: str) -> dict[str, Any] | None:
        """Get conversation with all messages.

        Args:
            thread_id: Thread identifier

        Returns:
            Dictionary with conversation details and messages, or None if not found
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row

            # Get conversation
            cursor = conn.execute(
                """
                SELECT
                    id, thread_id, command, model_name, summary,
                    created_at, updated_at
                FROM conversations
                WHERE thread_id = ?
            """,
                (thread_id,),
            )
            conv_row = cursor.fetchone()

            if conv_row is None:
                return None

            conversation = dict(conv_row)

            # Get messages
            cursor = conn.execute(
                """
                SELECT role, content, metadata, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """,
                (conversation["id"],),
            )

            messages = []
            for msg_row in cursor.fetchall():
                msg = dict(msg_row)
                if msg["metadata"]:
                    msg["metadata"] = json.loads(msg["metadata"])
                messages.append(msg)

            conversation["messages"] = messages
            return conversation
        finally:
            conn.close()

    def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent conversations.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of conversation summaries
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                """
                SELECT
                    c.thread_id,
                    c.command,
                    c.model_name,
                    c.summary,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_summary(self, thread_id: str, summary: str):
        """Update conversation summary.

        Args:
            thread_id: Thread identifier
            summary: New summary text
        """
        now = datetime.now(UTC).isoformat()

        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE conversations
                SET summary = ?, updated_at = ?
                WHERE thread_id = ?
            """,
                (summary, now, thread_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_conversation(self, thread_id: str) -> bool:
        """Delete a conversation and its messages.

        Args:
            thread_id: Thread identifier

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE thread_id = ?", (thread_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return False

            conversation_id = row[0]

            # Delete messages first (foreign key constraint)
            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )

            # Delete conversation
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

            conn.commit()
            return True
        finally:
            conn.close()

    def conversation_exists(self, thread_id: str) -> bool:
        """Check if a conversation exists.

        Args:
            thread_id: Thread identifier

        Returns:
            True if conversation exists
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM conversations WHERE thread_id = ? LIMIT 1", (thread_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
