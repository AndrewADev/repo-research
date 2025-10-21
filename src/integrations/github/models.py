from datetime import datetime
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class CommitChangeRecord(BaseModel):
    """Record of a single commit's changes to a file."""

    commit_sha: str = Field(..., description="Git commit SHA")
    commit_date: datetime = Field(..., description="When the commit was made")
    author_login: str | None = Field(None, description="GitHub login of the author")
    additions: int = Field(..., description="Lines added in this commit")
    deletions: int = Field(..., description="Lines deleted in this commit")
    total_lines_changed: int = Field(
        ..., description="Total lines affected (additions + deletions)"
    )


class CodeLineage(BaseModel):
    """Tracks when code lines were first introduced to detect rework."""

    file_path: str = Field(..., description="Path to the file")
    introduced_at: datetime = Field(
        ..., description="When these lines were first added"
    )
    introduced_by: str | None = Field(
        None, description="Author who introduced these lines"
    )
    commit_sha: str = Field(..., description="Commit that introduced these lines")
    line_count: int = Field(..., description="Number of lines in this lineage block")


class ReworkCategoryBreakdown(BaseModel):
    """Breakdown of code changes by category for rework rate analysis."""

    new_work_lines: int = Field(0, description="Lines of new work added")
    rework_lines: int = Field(
        0, description="Lines rewritten within 21 days of original commit"
    )
    refactor_lines: int = Field(0, description="Lines modified after 21 days")
    helping_others_lines: int = Field(
        0, description="Lines changed in someone else's recent code (within 21 days)"
    )

    @property
    def total_lines(self) -> int:
        """Total lines across all categories."""
        return (
            self.new_work_lines
            + self.rework_lines
            + self.refactor_lines
            + self.helping_others_lines
        )

    @property
    def rework_percentage(self) -> float:
        """Calculate rework percentage."""
        if self.total_lines == 0:
            return 0.0
        return (self.rework_lines / self.total_lines) * 100


class RepositoryRecord(BaseModel):
    """Internal model for tracking repositories in state."""

    name: str = Field(..., description="Full repository name (e.g., 'username/repo')")
    description: str | None = Field(None, description="Repository description")
    stars: int = Field(..., description="Number of stargazers")
    forks: int | None = Field(0, description="Number of forks")
    language: str | None = Field(None, description="Primary programming language")
    url: str = Field(..., description="HTML URL to the repository")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    pushed_at: datetime | None = Field(None, description="Last push timestamp")
    topics: list[str] = Field(default_factory=list, description="Repository topics")
    open_issues: int = Field(0, description="Number of open issues")
    size: int | None = Field(None, description="Repository size in KB")
    archived: bool = Field(False, description="Whether repository is archived")
    fork: bool = Field(False, description="Whether repository is a fork")
    private: bool = Field(False, description="Whether repository is private")
    license: str | None = Field(None, description="License key")


# Define input schemas for our tools
class StarredRepoInput(BaseModel):
    """Input schema for starred repositories tool using GitHub API native sorting."""

    username: str | None = Field(
        None, description="GitHub username. If not provided, uses authenticated user"
    )
    sort: Literal["created", "updated"] | None = Field(
        "updated",
        description=(
            "Sort by repository creation date or last update date. "
            "GitHub API native sort parameter."
        ),
    )
    direction: Literal["asc", "desc"] = Field(
        "desc", description="Sort direction (desc shows most recent first)"
    )
    per_page: int = Field(30, description="Number of results per page", ge=1, le=100)
    limit: int | None = Field(
        50,
        description=(
            "Maximum total results to return across all pages. If None, returns all."
        ),
        ge=1,
    )


class SearchRepoInput(BaseModel):
    """Input schema for repository search tool."""

    query: str = Field(
        ...,  # ... means required
        description="Search query string (e.g., 'language:python stars:>1000')",
    )
    sort: Literal["stars", "forks", "updated"] = Field(
        "stars", description="How to sort the results"
    )
    limit: int = Field(
        10, description="Maximum number of results to return", ge=1, le=100
    )


class ActivityAnalysisInput(BaseModel):
    """Input schema for repository activity analysis tool."""

    repo_full_name: str = Field(
        ..., description="Full repository name (e.g., 'username/repo')"
    )


class RateLimitInput(BaseModel):
    """Input schema for rate limit check tool."""

    pass


class TokenValidationInput(BaseModel):
    """Input schema for token validation tool."""

    pass


class RepositoryLabelsInput(BaseModel):
    """Input schema for repository labels tool."""

    repo_full_name: str = Field(
        ..., description="Full repository name (e.g., 'username/repo')"
    )


class RepositorySearchByTopicInput(BaseModel):
    """Input schema for repository search by topic tool."""

    topics: list[str] = Field(..., description="List of topic names to search for")
    sort: Literal["stars", "forks", "updated"] = Field(
        "updated", description="How to sort the results"
    )
    limit: int = Field(
        25, description="Maximum number of results to return", ge=1, le=100
    )
    language: str | None = Field(
        None,
        description="Programming language to filter by (e.g., 'python', 'javascript')",
    )
    license: str | None = Field(
        None,
        description="License type to filter by (e.g., 'mit', 'apache-2.0', 'gpl-3.0')",
    )
    min_stars: int | None = Field(25, description="Minimum number of stars", ge=0)
    max_stars: int | None = Field(None, description="Maximum number of stars", ge=0)
    min_forks: int | None = Field(None, description="Minimum number of forks", ge=0)
    max_forks: int | None = Field(None, description="Maximum number of forks", ge=0)
    created_after: str | None = Field(
        None, description="Created after date in YYYY-MM-DD format"
    )
    created_before: str | None = Field(
        None, description="Created before date in YYYY-MM-DD format"
    )
    updated_after: str | None = Field(
        None, description="Updated after date in YYYY-MM-DD format"
    )
    updated_before: str | None = Field(
        None, description="Updated before date in YYYY-MM-DD format"
    )
    pushed_after: str | None = Field(
        None, description="Last push after date in YYYY-MM-DD format"
    )
    pushed_before: str | None = Field(
        None, description="Last push before date in YYYY-MM-DD format"
    )
    archived: bool | None = Field(
        None,
        description="Filter by archived status (true for archived, false for active)",
    )
    template: bool | None = Field(
        None,
        description="Filter by template status (true for templates, false for regular)",
    )
    fork: bool | None = Field(
        None,
        description="Filter by fork status (true for forks, false for originals)",
    )
    is_public: bool | None = Field(
        None,
        description="Filter by visibility (true for public, false for private)",
    )
    size_min_kb: int | None = Field(
        None, description="Minimum repository size in kilobytes", ge=0
    )
    size_max_kb: int | None = Field(
        None, description="Maximum repository size in kilobytes", ge=0
    )


class QueryIssuesInput(BaseModel):
    """Input schema for querying repository issues."""

    repo_full_name: str = Field(
        ..., description="Full repository name (e.g., 'username/repo')"
    )
    labels: list[str] | None = Field(
        None, description="Filter by label names (e.g., ['bug', 'enhancement'])"
    )
    state: Literal["open", "closed", "all"] = Field(
        "open", description="Filter by issue state"
    )
    sort: Literal["created", "updated", "comments"] = Field(
        "created", description="Field to sort by"
    )
    direction: Literal["asc", "desc"] = Field(
        "desc", description="Sort direction (descending shows most recent first)"
    )
    limit: int = Field(
        10, description="Maximum number of results to return", ge=1, le=100
    )
    since: datetime | None = Field(
        None, description="Only show issues updated after this date (ISO 8601 format)"
    )


class CommitHotspotInput(BaseModel):
    """Input schema for commit hotspot analysis."""

    repo_full_name: str = Field(
        ..., description="Full repository name (e.g., 'username/repo')"
    )
    days: int = Field(
        180, description="Number of days of history to analyze", ge=1, le=365
    )
    max_commits: int = Field(
        500, description="Maximum commits to analyze", ge=1, le=1000
    )
    path: str | None = Field(
        None,
        description=(
            "Optional path to focus analysis (e.g., 'src/integrations' for drill-down)"
        ),
    )
    min_changes: int = Field(
        3,
        description=("Minimum changes required for a file to be considered a hotspot"),
        ge=1,
    )
    strategy: Literal["activity", "rework"] = Field(
        "activity",
        description=(
            "Churn calculation strategy: "
            "'activity' = total activity churn percentage "
            "(default, requires baseline LOC), "
            "'rework' = rework rate within 21 days"
        ),
    )


class FileHotspot(BaseModel):
    """Statistics for a single file hotspot."""

    file_path: str = Field(..., description="Path to the file in the repository")
    change_count: int = Field(..., description="Number of times file was changed")
    total_additions: int = Field(
        ..., description="Total lines added across all commits"
    )
    total_deletions: int = Field(
        ..., description="Total lines deleted across all commits"
    )
    churn_score: int | float = Field(
        ...,
        description=(
            "Churn score (metric varies by strategy): "
            "Simple: (additions + deletions) * change_count, "
            "Activity: percentage-based, "
            "Rework: rework percentage"
        ),
    )
    unique_authors: int = Field(
        ..., description="Number of unique authors who modified this file"
    )
    first_changed: datetime | None = Field(
        None, description="First commit date in analysis period"
    )
    last_changed: datetime | None = Field(
        None, description="Most recent commit date in analysis period"
    )
    baseline_loc: int | None = Field(
        None,
        description="Lines of code at start of analysis period (for activity churn)",
    )
    activity_churn_percentage: float | None = Field(
        None,
        description=(
            "Total activity churn: (additions + deletions) / baseline_loc × 100"
        ),
    )
    category_breakdown: ReworkCategoryBreakdown | None = Field(
        None, description="Breakdown by churn category (for rework rate strategy)"
    )
    rework_percentage: float | None = Field(
        None, description="Percentage of code that is rework (rewritten within 21 days)"
    )


class HotspotAnalysisResult(BaseModel):
    """Complete hotspot analysis result."""

    hotspots: list[FileHotspot] = Field(
        ..., description="List of file hotspots ranked by churn score"
    )
    analysis_period_days: int = Field(..., description="Number of days analyzed")
    total_commits_analyzed: int = Field(
        ..., description="Total number of commits processed"
    )
    total_files_changed: int = Field(..., description="Total unique files that changed")
    date_range_start: datetime = Field(..., description="Start of analysis period")
    date_range_end: datetime = Field(..., description="End of analysis period")
    path_filter: str | None = Field(None, description="Path filter applied, if any")


def add_repositories(
    existing: list[RepositoryRecord] | None, new: list[RepositoryRecord]
) -> list[RepositoryRecord]:
    """
    Reducer function for tracked_repositories that appends new repositories.

    Args:
        existing: Current list of tracked repositories
        new: New repositories to add

    Returns:
        Combined list of repositories
    """
    if existing is None:
        return new
    return existing + new


# Define our graph state
class GitHubToolState(TypedDict):
    """The state of our GitHub analysis graph."""

    # Messages have the type "list". The add_messages function defines how
    # this state key should be updated (appending messages rather than overwriting)
    messages: Annotated[list, add_messages]
    # Track how many steps we've taken to limit long-running operations
    step_count: int
    # Track the current entity type being searched for contextual error messages
    current_predicate: str | None
    # Track repositories returned by tools for downstream access
    tracked_repositories: Annotated[list[RepositoryRecord], add_repositories]
