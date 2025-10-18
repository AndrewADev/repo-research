"""Markdown export utilities for hotspot analysis results.

Provides strongly-typed export functionality to generate markdown reports
from hotspot analysis data and LLM conversation history.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ExportMetadata(BaseModel):
    """Metadata for a hotspot analysis export."""

    repo_name: str = Field(..., description="Full repository name (e.g., 'owner/repo')")
    analysis_date: datetime = Field(..., description="When the analysis was performed")
    latest_commit_sha: str | None = Field(
        ..., description="SHA of the most recent commit in analysis period"
    )
    output_dir: Path = Field(
        default=Path("./outputs"), description="Directory to save export files"
    )

    @property
    def sanitized_repo_name(self) -> str:
        """Return repo name with slashes replaced by hyphens."""
        return self.repo_name.replace("/", "-")

    @property
    def short_sha(self) -> str | None:
        """Return abbreviated commit SHA (first 7 characters)."""
        return (
            self.latest_commit_sha[:7]
            if self.latest_commit_sha
            else self.latest_commit_sha
        )

    @property
    def filename(self) -> str:
        """Generate filename in format: repo-name_sha_DD-MM-YYYY-HHmm.md"""
        date_str = self.analysis_date.strftime("%d-%m-%Y")
        time_str = self.analysis_date.strftime("%H%M")
        return (
            f"{self.sanitized_repo_name}_{self.short_sha}_{date_str}-{time_str}.md"
            if self.short_sha
            else f"{self.sanitized_repo_name}_{date_str}-{time_str}.md"
        )

    @property
    def filepath(self) -> Path:
        """Return full filepath for the export."""
        return self.output_dir / self.filename
