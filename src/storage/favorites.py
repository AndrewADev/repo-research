"""Server-side favorites storage, sharing the agents' SQLite database.

Favorites used to live only in browser localStorage (the Gradio ``BrowserState``).
They now persist in the **same** ``~/.repo-research/conversations.db`` that holds
conversation metadata and LangGraph checkpoints, following the same pattern as
``ConversationStore`` (plain ``sqlite3``, an ``_init_db`` that creates its table
``IF NOT EXISTS``, and a context-manager interface).

The ``SavedRepository`` / ``FavoritesState`` Pydantic models also live here so
both the React SPA (via the API) and the legacy Gradio UI share one definition.
"""

import json
import sqlite3
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Literal

from pydantic import BaseModel, Field

from integrations.github.models import RepositoryRecord
from storage.conversations import default_db_path


class SavedRepository(BaseModel):
    """Represents a saved/favorited repository."""

    full_name: str = Field(..., description="e.g., 'owner/repo'")
    url: str
    stars: int
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    description: str = ""
    saved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_repository_record(cls, repo: RepositoryRecord) -> "SavedRepository":
        """Convert a ``RepositoryRecord`` (graph state) to a ``SavedRepository``."""
        return cls(
            full_name=repo.name,
            url=repo.url,
            stars=repo.stars,
            language=repo.language or "",
            topics=repo.topics,
            description=repo.description or "",
            saved_at=datetime.now(UTC),
        )


class FavoritesState(BaseModel):
    """A collection of saved repositories (used by the legacy Gradio UI)."""

    saved_repos: list[SavedRepository] = Field(default_factory=list)

    def add_repository(self, repo: SavedRepository) -> bool:
        """Add repo if not already saved. Returns True if added."""
        if any(r.full_name == repo.full_name for r in self.saved_repos):
            return False
        self.saved_repos.insert(0, repo)
        return True

    def remove_repository(self, full_name: str) -> bool:
        """Remove repo by name. Returns True if found and removed."""
        before_len = len(self.saved_repos)
        self.saved_repos = [r for r in self.saved_repos if r.full_name != full_name]
        return len(self.saved_repos) < before_len

    def is_repository_saved(self, full_name: str) -> bool:
        """Check if a repository is already saved."""
        return any(r.full_name == full_name for r in self.saved_repos)

    def get_table_data(self) -> list[list[Any]]:
        """Get repositories formatted for a table display."""
        rows: list[list[Any]] = []
        for repo in self.saved_repos:
            rows.append(
                [
                    repo.full_name,
                    repo.url,
                    repo.stars,
                    repo.language,
                    ", ".join(repo.topics[:5]),  # Limit to 5 topics
                    repo.description[:100],  # Truncate description
                    repo.saved_at.isoformat()[:19],  # Remove microseconds/timezone
                ]
            )
        return rows

    def export_csv(self) -> str:
        """Export favorites as a CSV string."""
        lines = ["full_name,url,stars,language,topics,description,saved_at"]

        for repo in self.saved_repos:
            topics = ";".join(repo.topics)
            description = repo.description.replace(",", ";").replace("\n", " ")

            lines.append(
                f"{repo.full_name},"
                f"{repo.url},"
                f"{repo.stars},"
                f"{repo.language},"
                f'"{topics}",'
                f'"{description}",'
                f"{repo.saved_at.isoformat()}"
            )

        return "\n".join(lines)


class FavoriteStore:
    """SQLite-backed favorites persistence in the shared conversations DB."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the favorites store.

        Args:
            db_path: Path to the SQLite database. Defaults to the same file used
                by ``ConversationStore`` (``~/.repo-research/conversations.db``).
        """
        self.db_path = db_path if db_path is not None else default_db_path()
        self._init_db()

    def __enter__(self) -> "FavoriteStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self.close()
        return False

    def close(self) -> None:
        """No long-lived connection is held; present for interface symmetry."""
        return None

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    full_name TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    stars INTEGER NOT NULL DEFAULT 0,
                    language TEXT NOT NULL DEFAULT '',
                    topics TEXT NOT NULL DEFAULT '[]',
                    description TEXT NOT NULL DEFAULT '',
                    saved_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def add(self, repo: SavedRepository) -> bool:
        """Insert a favorite. Returns True if newly added, False if it existed."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO favorites
                (full_name, url, stars, language, topics, description, saved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo.full_name,
                    repo.url,
                    repo.stars,
                    repo.language,
                    json.dumps(repo.topics),
                    repo.description,
                    repo.saved_at.isoformat(),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def remove(self, full_name: str) -> bool:
        """Delete a favorite by full name. Returns True if a row was removed."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM favorites WHERE full_name = ?", (full_name,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list(self) -> list[SavedRepository]:
        """Return all favorites, most recently saved first."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM favorites ORDER BY saved_at DESC"
            ).fetchall()
            return [
                SavedRepository(
                    full_name=row["full_name"],
                    url=row["url"],
                    stars=row["stars"],
                    language=row["language"],
                    topics=json.loads(row["topics"]),
                    description=row["description"],
                    saved_at=datetime.fromisoformat(row["saved_at"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def export_csv(self) -> str:
        """Export all favorites as a CSV string."""
        return FavoritesState(saved_repos=self.list()).export_csv()
