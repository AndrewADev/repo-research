

from typing import Annotated, Literal, Optional, TypedDict
from pydantic import BaseModel, Field

from langgraph.graph.message import add_messages

# Define input schemas for our tools
class StarredRepoInput(BaseModel):
    """Input schema for starred repositories tool."""
    username: Optional[str] = Field(
        None, 
        description="GitHub username. If not provided, uses authenticated user"
    )
    sort_by: Literal["stars", "recent", "issues"] = Field(
        "stars",
        description="How to sort the results"
    )

class SearchRepoInput(BaseModel):
    """Input schema for repository search tool."""
    query: str = Field(
        ...,  # ... means required
        description="Search query string (e.g., 'language:python stars:>1000')"
    )
    sort: Literal["stars", "forks", "updated"] = Field(
        "stars",
        description="How to sort the results"
    )
    limit: int = Field(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )

class ActivityAnalysisInput(BaseModel):
    """Input schema for repository activity analysis tool."""
    repo_full_name: str = Field(
        ...,
        description="Full repository name (e.g., 'username/repo')"
    )

class RateLimitInput(BaseModel):
    """Input schema for rate limit check tool."""
    pass

# Define our graph state
class GitHubToolState(TypedDict):
    """The state of our GitHub analysis graph."""
    # Messages have the type "list". The add_messages function defines how 
    # this state key should be updated (appending messages rather than overwriting)
    messages: Annotated[list, add_messages]
    # Track how many steps we've taken to limit long-running operations
    step_count: int
