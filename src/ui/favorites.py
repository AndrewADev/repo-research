"""Repository favorites management for browser-based storage."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from integrations.github.models import RepositoryRecord


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
        """Convert RepositoryRecord to SavedRepository."""
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
    """Browser state for saved repositories."""

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

    def get_table_data(self) -> list[list]:
        """Get repositories formatted for Gradio table display."""
        rows = []
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
        """Export favorites as CSV string."""
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
