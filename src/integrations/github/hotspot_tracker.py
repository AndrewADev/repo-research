"""
File change tracking for hotspot analysis.

Provides strongly-typed tracking of file changes across commits,
replacing the dict[str, dict] pattern with proper classes.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .churn_strategies import (
    DEFAULT_STRATEGY,
    ChurnCalculationStrategy,
    ReworkRateStrategy,
    TotalActivityChurnStrategy,
)
from .models import CommitChangeRecord, FileHotspot


class FileStatistics(BaseModel):
    """Internal statistics for a single file across multiple commits."""

    change_count: int = Field(0, description="Number of times file was changed")
    total_additions: int = Field(0, description="Total lines added")
    total_deletions: int = Field(0, description="Total lines deleted")
    authors: set[str] = Field(default_factory=set, description="Unique author logins")
    first_changed: datetime | None = Field(None, description="First change date")
    last_changed: datetime | None = Field(None, description="Last change date")
    commit_history: list[CommitChangeRecord] = Field(
        default_factory=list,
        description="Chronological list of commits affecting this file",
    )
    baseline_loc: int | None = Field(
        None, description="Lines of code at start of analysis period"
    )


class FileChangeTracker:
    """
    Tracks aggregated file change statistics across commits.

    Replaces the dict[str, dict] pattern with strongly-typed tracking
    and pluggable churn calculation strategies.
    """

    def __init__(self, strategy: ChurnCalculationStrategy = DEFAULT_STRATEGY) -> None:
        """
        Initialize the file change tracker.

        Args:
            strategy: Churn calculation strategy to use
        """
        self.strategy = strategy
        self._stats: dict[str, FileStatistics] = {}

    def record_file_change(
        self,
        file_path: str,
        additions: int,
        deletions: int,
        author_login: str | None,
        commit_date: datetime,
        commit_sha: str | None = None,
    ) -> None:
        """
        Record a file change from a commit.

        Args:
            file_path: Path to the file in the repository
            additions: Number of lines added in this commit
            deletions: Number of lines deleted in this commit
            author_login: GitHub login of the commit author (None if not available)
            commit_date: Date of the commit
            commit_sha: Git commit SHA (optional, for detailed tracking)
        """
        # Initialize statistics for new files
        if file_path not in self._stats:
            self._stats[file_path] = FileStatistics(
                first_changed=commit_date, last_changed=commit_date
            )

        # Update statistics
        stats = self._stats[file_path]
        stats.change_count += 1
        stats.total_additions += additions
        stats.total_deletions += deletions

        # Track author (if available)
        if author_login:
            stats.authors.add(author_login)

        # Record commit history for temporal analysis
        if commit_sha:
            commit_record = CommitChangeRecord(
                commit_sha=commit_sha,
                commit_date=commit_date,
                author_login=author_login,
                additions=additions,
                deletions=deletions,
                total_lines_changed=additions + deletions,
            )
            stats.commit_history.append(commit_record)

        # Update date range
        if stats.first_changed is None or commit_date < stats.first_changed:
            stats.first_changed = commit_date
        if stats.last_changed is None or commit_date > stats.last_changed:
            stats.last_changed = commit_date

    def set_baseline_loc(self, file_path: str, loc: int) -> None:
        """
        Set the baseline LOC for a file (LOC at start of analysis period).

        Args:
            file_path: Path to the file
            loc: Lines of code at baseline
        """
        if file_path in self._stats:
            self._stats[file_path].baseline_loc = loc

    def get_hotspots(self, min_changes: int) -> list[FileHotspot]:
        """
        Calculate and return hotspots sorted by churn score.

        Args:
            min_changes: Minimum number of changes required for a file to be included

        Returns:
            List of FileHotspot objects, sorted by churn score (highest first)
        """
        hotspots = []

        for file_path, stats in self._stats.items():
            # Apply min_changes filter
            if stats.change_count < min_changes:
                continue

            # Prepare common protocol parameters (shared by all strategies)
            common_params = {
                "commit_history": stats.commit_history,
            }

            # Initialize optional fields
            churn_score: int | float
            baseline_loc = None
            activity_churn_percentage = None
            category_breakdown = None
            rework_percentage = None

            # Calculate churn score based on strategy type
            if isinstance(self.strategy, TotalActivityChurnStrategy):
                # Add strategy-specific parameter
                churn_score = self.strategy.calculate_churn(
                    **common_params,
                    baseline_loc=stats.baseline_loc,
                )
                baseline_loc = stats.baseline_loc
                activity_churn_percentage = churn_score

            elif isinstance(self.strategy, ReworkRateStrategy):
                churn_score, category_breakdown = self.strategy.calculate_churn(
                    **common_params
                )
                rework_percentage = churn_score

            else:
                # Simple or Author strategies
                churn_score = self.strategy.calculate_churn(**common_params)

            hotspot = FileHotspot(
                file_path=file_path,
                change_count=stats.change_count,
                total_additions=stats.total_additions,
                total_deletions=stats.total_deletions,
                churn_score=churn_score,
                unique_authors=len(stats.authors),
                first_changed=stats.first_changed,
                last_changed=stats.last_changed,
                baseline_loc=baseline_loc,
                activity_churn_percentage=activity_churn_percentage,
                category_breakdown=category_breakdown,
                rework_percentage=rework_percentage,
            )
            hotspots.append(hotspot)

        # Sort by churn score (highest first)
        hotspots.sort(key=lambda x: x.churn_score, reverse=True)

        return hotspots

    @property
    def total_files_changed(self) -> int:
        """Return the total number of unique files that have been tracked."""
        return len(self._stats)
