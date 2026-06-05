"""
LangChain GitHub Tools Integration with Anthropic's Claude and Pydantic schemas.

This module integrates GitHub tools with LangGraph's framework, using proper Pydantic
models for input validation and schema generation.

"""

import json
from functools import wraps
from typing import Annotated

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, StructuredTool
from langgraph.types import Command
from pydantic import BaseModel

from tools.utils import generate_tool_call_id

from .models import (
    ActivityAnalysisInput,
    CommitHotspotInput,
    GitHubToolState,
    QueryIssuesInput,
    RateLimitInput,
    RepositoryLabelsInput,
    RepositoryRecord,
    RepositorySearchByTopicInput,
    SearchRepoInput,
    StarredRepoInput,
    TokenValidationInput,
)
from .tools import GitHubTools


def parse_repository_data(repo_dict: dict) -> RepositoryRecord:
    """
    Convert a repository dictionary from tools.py into a RepositoryRecord.

    Args:
        repo_dict: Repository data dictionary from GitHub API

    Returns:
        RepositoryRecord instance
    """
    return RepositoryRecord(
        name=repo_dict.get("name", ""),
        description=repo_dict.get("description"),
        stars=repo_dict.get("stars", 0),
        forks=repo_dict.get("forks", 0),
        language=repo_dict.get("language"),
        url=repo_dict.get("url", ""),
        updated_at=repo_dict.get("updated_at"),
        created_at=repo_dict.get("created_at"),
        pushed_at=repo_dict.get("pushed_at"),
        topics=repo_dict.get("topics", []),
        open_issues=repo_dict.get("open_issues", 0),
        size=repo_dict.get("size"),
        archived=repo_dict.get("archived", False),
        fork=repo_dict.get("fork", False),
        private=repo_dict.get("private", False),
        license=repo_dict.get("license"),
    )


def with_github_tools(func):
    """Decorator to handle GitHub tool lifecycle."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        github_tools = GitHubTools()
        try:
            return func(*args, **kwargs, github_tools=github_tools)
        finally:
            github_tools.close()

    return wrapper


class StarredRepositoriesTool(BaseTool):
    name: str = "get_starred_repositories"
    description: str = """
    Retrieve repositories starred by a GitHub user with native GitHub API sorting.
    Supports sorting by repository creation date or last update date.
    Useful for understanding user interests and finding recently active projects.
    """
    args_schema: type[BaseModel] = StarredRepoInput

    @with_github_tools
    def _run(
        self,
        username: str | None = None,
        sort: str | None = None,
        direction: str = "desc",
        per_page: int = 30,
        limit: int | None = None,
        tool_call_id: Annotated[str, InjectedToolCallId] = None,
        github_tools: GitHubTools | None = None,
    ) -> Command:
        """Execute the starred repositories tool."""
        try:
            tool_call_id = (
                generate_tool_call_id("get_starred_repositories")
                if tool_call_id is None
                else tool_call_id
            )

            repos = github_tools.get_starred_repositories(
                username=username,
                sort=sort,
                direction=direction,
                per_page=per_page,
                limit=limit,
            )

            # Enhanced response with metadata
            response = {
                "results": repos,
                "search_metadata": {
                    "username": username or "authenticated_user",
                    "sort": sort,
                    "direction": direction,
                    "per_page": per_page,
                    "limit": limit,
                    "total_found": len(repos),
                    "has_results": len(repos) > 0,
                },
            }

            # Add specific messaging for no results
            if len(repos) == 0:
                user_display = username or "the authenticated user"
                response["search_metadata"]["suggestion"] = (
                    f"No starred repositories found for {user_display}. "
                    "Consider: 1) Verifying the username is correct, "
                    "2) Checking if the user has any starred repositories, "
                    "3) Trying a different user, or 4) Asking for alternative analysis."
                )

            # Convert repos to RepositoryRecord objects
            tracked_repos = [parse_repository_data(repo) for repo in repos]

            # Return Command to update state
            return Command(
                update={
                    "tracked_repositories": tracked_repos,
                    "messages": [
                        ToolMessage(
                            content=json.dumps(response, default=str, indent=2),
                            tool_call_id=tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )
        except Exception as e:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"error": str(e)}),
                            tool_call_id=tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )


class RepositorySearchTool(StructuredTool):
    name: str = "search_repositories"
    description: str = """
    Search for GitHub repositories matching specific criteria.
    Useful for finding repositories based on language, stars, topics, etc.
    """
    args_schema: type[BaseModel] = SearchRepoInput

    @with_github_tools
    def _run(
        self,
        query: str,
        sort: str = "stars",
        limit: int = 10,
        tool_call_id: Annotated[str, InjectedToolCallId] = None,
        github_tools: GitHubTools | None = None,
    ) -> Command:
        """Execute the repository search tool."""
        try:
            results = github_tools.search_repositories(query, sort, limit)

            # Enhanced response with search metadata
            response = {
                "results": results,
                "search_metadata": {
                    "query": query,
                    "total_found": len(results),
                    "has_results": len(results) > 0,
                },
            }

            # Add specific messaging for no results
            if len(results) == 0:
                response["search_metadata"]["suggestion"] = (
                    "No repositories found for this query. Consider: "
                    "1) Broadening search terms, 2) Checking spelling, "
                    "3) Using different keywords, or "
                    "4) Asking the user for alternative search criteria."
                )

            # Convert repos to RepositoryRecord objects
            tracked_repos = [parse_repository_data(repo) for repo in results]

            # Return Command to update state
            return Command(
                update={
                    "tracked_repositories": tracked_repos,
                    "messages": [
                        ToolMessage(
                            content=json.dumps(response, default=str, indent=2),
                            tool_call_id=tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )
        except Exception as e:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"error": str(e)}),
                            tool_call_id=tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )


# @tool(args_schema=ActivityAnalysisInput)
class RepositoryActivityTool(StructuredTool):
    name: str = "analyze_repository_activity"
    description: str = """
    Analyze recent activity in a GitHub repository.
    Useful for understanding how active and maintained a repository is.
    """
    args_schema: type[BaseModel] = ActivityAnalysisInput

    @with_github_tools
    def _run(self, repo_full_name: str, github_tools: GitHubTools | None = None) -> str:
        """Execute the repository activity analysis tool."""
        try:
            activity = github_tools.analyze_repository_activity(repo_full_name)
            return json.dumps(activity, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class RateLimitCheckTool(StructuredTool):
    name: str = "check_rate_limit_status"
    description: str = """
    Check the current GitHub API rate limit status for the configured token.
    Shows remaining requests and reset times for core API, search API, and GraphQL API.
    Useful for understanding API quota usage and planning API calls.
    """
    args_schema: type[BaseModel] = RateLimitInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None) -> str:
        """Execute the rate limit check tool."""
        try:
            status = github_tools.check_rate_limit_status()
            return json.dumps(status, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class TokenValidationTool(StructuredTool):
    name: str = "validate_github_token"
    description: str = """
    Validate the GitHub token and return detailed information about its capabilities.
    Checks if the token is valid, what permissions it has, and provides rate
    limit status. Useful for debugging authentication issues and understanding
    token scope.
    """
    args_schema: type[BaseModel] = TokenValidationInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None) -> str:
        """Execute the token validation tool."""
        try:
            validation_result = github_tools.validate_token()
            return json.dumps(validation_result, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class RepositoryLabelsTool(StructuredTool):
    name: str = "get_repository_labels"
    description: str = """
    Retrieve all labels from a specific GitHub repository.
    Useful for understanding the labeling system and organization of
    issues/PRs in a repository.

    Returns label names, colors, descriptions, and URLs.
    """
    args_schema: type[BaseModel] = RepositoryLabelsInput

    @with_github_tools
    def _run(self, repo_full_name: str, github_tools: GitHubTools | None = None) -> str:
        """Execute the repository labels tool."""
        try:
            labels = github_tools.get_repository_labels(repo_full_name)
            return json.dumps(labels, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class RepositorySearchByTopicTool(StructuredTool):
    name: str = "search_repositories_by_topic"
    description: str = """
    Search for GitHub repositories that have specific topics assigned.
    Useful for discovering repositories by technology, category, or purpose.
    Returns repositories with their topics and matches the specified topic criteria.
    """
    args_schema: type[BaseModel] = RepositorySearchByTopicInput

    @with_github_tools
    def _run(
        self,
        tool_call_id: Annotated[str, InjectedToolCallId] = None,
        github_tools: GitHubTools | None = None,
        **kwargs,
    ) -> Command:
        """Execute the repository search by topic tool."""
        try:
            # Create the search parameters model from the kwargs
            search_params = RepositorySearchByTopicInput(**kwargs)

            tool_call_id = (
                generate_tool_call_id("search_repositories_by_topic")
                if tool_call_id is None
                else tool_call_id
            )

            results = github_tools.search_repositories_by_topic(search_params)

            # Enhanced response with search metadata
            response = {
                "results": results,
                "search_metadata": {
                    "topics_searched": search_params.topics,
                    "total_found": len(results),
                    "has_results": len(results) > 0,
                    "search_parameters": {
                        "language": search_params.language,
                        "min_stars": search_params.min_stars,
                        "sort": search_params.sort,
                    },
                },
            }

            # Add specific messaging for no results
            if len(results) == 0:
                response["search_metadata"]["suggestion"] = (
                    f"No repositories found with topics {search_params.topics}. "
                    "Consider: 1) Trying broader or different topics, "
                    "2) Relaxing filters (stars, language), "
                    "3) Checking topic spelling, or "
                    "4) Asking the user for alternative topics to search."
                )

            # Convert repos to RepositoryRecord objects
            tracked_repos = [parse_repository_data(repo) for repo in results]

            # Return Command to update state
            return Command(
                update={
                    "tracked_repositories": tracked_repos,
                    "messages": [
                        ToolMessage(
                            content=json.dumps(response, default=str, indent=2),
                            tool_call_id=tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )
        except Exception as e:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=json.dumps({"error": str(e)}),
                            tool_call_id=tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )


class QueryIssuesTool(StructuredTool):
    name: str = "query_issues"
    description: str = """
    Query issues from a GitHub repository with advanced filtering and sorting.
    Useful for finding recent issues, issues with specific labels, or
    analyzing issue trends. Automatically filters out pull requests,
    returning only actual issues. Supports filtering by state
    (open/closed/all), labels, and date ranges.
    """
    args_schema: type[BaseModel] = QueryIssuesInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None, **kwargs) -> str:
        """Execute the query issues tool."""
        try:
            # Create the query parameters model from the kwargs
            query_params = QueryIssuesInput(**kwargs)

            results = github_tools.query_issues(query_params)

            # Enhanced response with search metadata
            response = {
                "results": results,
                "search_metadata": {
                    "repository": query_params.repo_full_name,
                    "total_found": len(results),
                    "has_results": len(results) > 0,
                    "filters_applied": {
                        "state": query_params.state,
                        "labels": query_params.labels,
                        "sort": query_params.sort,
                        "direction": query_params.direction,
                        "since": query_params.since,
                    },
                },
            }

            # Add specific messaging for no results
            if len(results) == 0:
                response["search_metadata"]["suggestion"] = (
                    f"No issues found in {query_params.repo_full_name} "
                    f"with the specified filters. Consider: "
                    "1) Checking if the repository has issues, "
                    "2) Trying different state ('all' instead of 'open'), "
                    "3) Removing or changing label filters, or "
                    "4) Adjusting the date range."
                )

            return json.dumps(response, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class CommitHotspotAnalysisTool(StructuredTool):
    name: str = "analyze_commit_hotspots"
    description: str = """
    Analyze repository maintenance hotspots by examining commit history.
    Identifies files that change frequently, which may indicate architectural
    issues, complexity, or areas needing refactoring. Returns files ranked
    by churn score (a combination of change frequency and size of changes).
    Useful for identifying technical debt and planning refactoring efforts.
    Supports optional path filtering for drill-down analysis.
    """
    args_schema: type[BaseModel] = CommitHotspotInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None, **kwargs) -> str:
        """Execute the commit hotspot analysis tool."""
        try:
            # Create the analysis parameters model from the kwargs
            hotspot_params = CommitHotspotInput(**kwargs)

            results = github_tools.analyze_commit_hotspots(hotspot_params)

            # Enhanced response with analysis metadata
            response = {
                "results": results,
                "analysis_metadata": {
                    "repository": hotspot_params.repo_full_name,
                    "period_analyzed": f"{results['analysis_period_days']} days",
                    "commits_processed": results["total_commits_analyzed"],
                    "files_analyzed": results["total_files_changed"],
                    "hotspots_found": len(results["hotspots"]),
                    "path_filter": results["path_filter"],
                    "min_changes_threshold": hotspot_params.min_changes,
                },
            }

            # Add specific messaging for no hotspots found
            if len(results["hotspots"]) == 0:
                min_changes = hotspot_params.min_changes
                repo_name = hotspot_params.repo_full_name
                response["analysis_metadata"]["suggestion"] = (
                    f"No hotspots found in {repo_name} "
                    f"matching the criteria (min {min_changes} changes). "
                    "Consider: "
                    "1) Lowering min_changes threshold, "
                    "2) Increasing the analysis period (days parameter), "
                    "3) Checking if the repository has recent commits, or "
                    "4) Removing path filter if applied."
                )

            return json.dumps(response, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


def result_analysis_condition(state: GitHubToolState) -> str:
    """Analyze tool results for errors and no-results scenarios."""
    messages = state.get("messages", [])
    if not messages:
        return "continue"

    last_message = messages[-1]
    if hasattr(last_message, "content") and last_message.content:
        content = last_message.content.lower()

        # Check for explicit errors first
        if "error" in content:
            return "run_diagnostics"

        # Check for no-results scenarios
        no_results_indicators = [
            '"has_results": false',
            '"total_found": 0',
            "no repositories found",
            "no results",
            "consider: 1) broadening search terms",
        ]

        if any(indicator in content for indicator in no_results_indicators):
            return "handle_no_results"

    return "continue"


def handle_no_results_node(state: GitHubToolState):
    """Handle no-results scenarios by automatically concluding gracefully."""
    # Get the entity type from state, defaulting to generic "results"
    entity_type = state.get("current_predicate", "results")

    no_results_message = AIMessage(
        content=(
            f"🔍 **No Results Found - Task Concluded**\n\n"
            f"The search didn't return any {entity_type} matching the criteria. "
            "This could indicate:\n\n"
            "- The specific combination of topics/filters is very rare\n"
            "- The search terms might need adjustment\n"
            f"- The desired {entity_type} may not exist or be publicly available\n\n"
            "To try a different search, please run the command again with "
            "different topics or search criteria."
        )
    )

    return {"messages": [no_results_message], "task_concluded": True}


def run_diagnostics_node(state: GitHubToolState):
    """Run the existing diagnostic workflow."""
    from core.prompts import run_diagnostic

    diagnostic_message = AIMessage(
        content=(
            "🔍 **Error Detected - Running Diagnostics**\n\n"
            f"{run_diagnostic.content}"
            "Are we able to continue our task?"
        )
    )

    return {"messages": [diagnostic_message], "diagnostic_ran": True}


def can_continue_condition(state: GitHubToolState) -> str:
    """Check if we can continue after diagnostics based on LLM response."""
    messages = state.get("messages", [])
    if not messages:
        return "continue"

    # Look for the LLM's response to the diagnostic prompt
    # Check if the latest message indicates we should stop
    last_message = messages[-1]
    if hasattr(last_message, "content") and last_message.content:
        content = last_message.content.lower()

        # Look for negative responses to "Are we able to continue our task?"
        stop_indicators = [
            "no",
            "not able",
            "cannot continue",
            "unable to continue",
            "should stop",
            "cannot proceed",
            "not possible",
            "blocked",
            "failed",
            "critical error",
            "cannot resolve",
        ]

        if any(indicator in content for indicator in stop_indicators):
            return "stop"

    return "continue"


def diagnostic_stop_node(state: GitHubToolState):
    """Node that provides a clear stop message for main.py to detect."""
    stop_message = AIMessage(
        content=(
            "⚠️ **Execution Stopped Due to Diagnostics**\n\n"
            "Diagnostics indicate we cannot continue."
            "Stopping execution to prevent further issues."
        )
    )

    return {"messages": [stop_message], "execution_stopped": True}
