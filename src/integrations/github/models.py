from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# Define input schemas for our tools
class StarredRepoInput(BaseModel):
    """Input schema for starred repositories tool."""

    username: str | None = Field(
        None, description="GitHub username. If not provided, uses authenticated user"
    )
    sort_by: Literal["stars", "recent", "issues"] = Field(
        "stars", description="How to sort the results"
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
    sort: Literal["stars", "forks", "updated", "created", "pushed", "full_name"] = (
        Field("updated", description="How to sort the results")
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


# Define our graph state
class GitHubToolState(TypedDict):
    """The state of our GitHub analysis graph."""

    # Messages have the type "list". The add_messages function defines how
    # this state key should be updated (appending messages rather than overwriting)
    messages: Annotated[list, add_messages]
    # Track how many steps we've taken to limit long-running operations
    step_count: int
