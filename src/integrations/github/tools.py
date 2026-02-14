"""
GitHub API Tool Methods for AI Agents

This module provides a collection of functions for interacting with GitHub's API,
specifically designed to be used as tools by an AI agent. Each function is
self-contained and handles its own error checking and rate limiting.

Requirements:
    - requests
    - python-dotenv
"""

import os
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from .github_client import GitHubAPIError, GitHubClient

if TYPE_CHECKING:
    from .models import (
        CommitHotspotInput,
        QueryIssuesInput,
        RepositorySearchByTopicInput,
    )


def build_repository_search_query(search_params: "RepositorySearchByTopicInput") -> str:
    """
    Build a GitHub search query string from search parameters.

    Args:
        search_params: RepositorySearchByTopicInput with search criteria

    Returns:
        GitHub search query string
    """
    query_parts = [f"topic:{topic}" for topic in search_params.topics]

    # Add language filter
    if search_params.language:
        query_parts.append(f"language:{search_params.language}")

    # Add license filter
    if search_params.license:
        query_parts.append(f"license:{search_params.license}")

    # Add star filters
    if search_params.min_stars is not None and search_params.max_stars is not None:
        query_parts.append(
            f"stars:{search_params.min_stars}..{search_params.max_stars}"
        )
    elif search_params.min_stars is not None:
        query_parts.append(f"stars:>={search_params.min_stars}")
    elif search_params.max_stars is not None:
        query_parts.append(f"stars:<={search_params.max_stars}")

    # Add fork filters
    if search_params.min_forks is not None and search_params.max_forks is not None:
        query_parts.append(
            f"forks:{search_params.min_forks}..{search_params.max_forks}"
        )
    elif search_params.min_forks is not None:
        query_parts.append(f"forks:>={search_params.min_forks}")
    elif search_params.max_forks is not None:
        query_parts.append(f"forks:<={search_params.max_forks}")

    # Add date filters
    if search_params.created_after and search_params.created_before:
        query_parts.append(
            f"created:{search_params.created_after}..{search_params.created_before}"
        )
    elif search_params.created_after:
        query_parts.append(f"created:>={search_params.created_after}")
    elif search_params.created_before:
        query_parts.append(f"created:<={search_params.created_before}")

    if search_params.updated_after and search_params.updated_before:
        query_parts.append(
            f"updated:{search_params.updated_after}..{search_params.updated_before}"
        )
    elif search_params.updated_after:
        query_parts.append(f"updated:>={search_params.updated_after}")
    elif search_params.updated_before:
        query_parts.append(f"updated:<={search_params.updated_before}")

    if search_params.pushed_after and search_params.pushed_before:
        query_parts.append(
            f"pushed:{search_params.pushed_after}..{search_params.pushed_before}"
        )
    elif search_params.pushed_after:
        query_parts.append(f"pushed:>={search_params.pushed_after}")
    elif search_params.pushed_before:
        query_parts.append(f"pushed:<={search_params.pushed_before}")

    # Add size filters
    if search_params.size_min_kb is not None and search_params.size_max_kb is not None:
        query_parts.append(
            f"size:{search_params.size_min_kb}..{search_params.size_max_kb}"
        )
    elif search_params.size_min_kb is not None:
        query_parts.append(f"size:>={search_params.size_min_kb}")
    elif search_params.size_max_kb is not None:
        query_parts.append(f"size:<={search_params.size_max_kb}")

    # Add boolean filters
    if search_params.archived is not None:
        query_parts.append(f"archived:{str(search_params.archived).lower()}")

    if search_params.template is not None:
        query_parts.append(f"template:{str(search_params.template).lower()}")

    if search_params.fork is not None:
        query_parts.append(f"fork:{str(search_params.fork).lower()}")

    if search_params.is_public is not None:
        if search_params.is_public:
            query_parts.append("is:public")
        else:
            query_parts.append("is:private")

    return " ".join(query_parts)


class GitHubTools:
    def __init__(self, token: str | None = None):
        """
        Initialize GitHub tools with authentication.

        Args:
            token: GitHub personal access token. If None, will try to load
              from environment.
        """
        # Load environment variables if token not provided
        if token is None:
            load_dotenv()
            token = os.getenv("GITHUB_TOKEN")

        if not token:
            raise ValueError("GitHub token not provided and not found in environment")

        self.client = GitHubClient(token)

    def _handle_rate_limit(self) -> None:
        """Check rate limit and sleep if necessary."""
        self.client.check_rate_limit_and_wait()

    def get_starred_repositories(
        self,
        username: str | None = None,
        sort: str | None = "updated",
        direction: str = "desc",
        per_page: int = 30,
        limit: int | None = 50,
    ) -> list[dict]:
        """
        Retrieve starred repositories for a user using GitHub API's native sorting.

        Args:
            username: GitHub username. If None, uses authenticated user.
            sort: Sort by 'created' or 'updated'. (default: 'updated').
            direction: Sort direction - 'asc' or 'desc' (default: 'desc')
            per_page: Number of results per page (default: 30, max: 100)
            limit: Maximum total results to return. If None, returns all.

        Returns:
            List of dictionaries containing repository information
        """
        try:
            self._handle_rate_limit()

            # Get starred repos from our custom client
            if username:
                endpoint = f"/users/{username}/starred"
            else:
                endpoint = "/user/starred"

            # Build query parameters
            params: dict[str, str | int] = {"per_page": per_page}
            if sort:
                params["sort"] = sort
                params["direction"] = direction

            starred_repos = []
            page = 1

            # Custom header to get topics
            custom_headers = {"Accept": "application/vnd.github.mercy-preview+json"}

            while True:
                # Add page parameter
                params["page"] = page

                # Make API call
                data = self.client.get(endpoint, params, custom_headers=custom_headers)

                if not data:
                    break

                # Parse repository data
                for repo in data:
                    # Parse ISO datetime strings, removing 'Z' suffix
                    updated_at_str = repo.get("updated_at")
                    created_at_str = repo.get("created_at")
                    pushed_at_str = repo.get("pushed_at")

                    repo_data = {
                        "name": repo.get("full_name"),
                        "description": repo.get("description"),
                        "stars": repo.get("stargazers_count", 0),
                        "updated_at": datetime.fromisoformat(
                            updated_at_str.replace("Z", "+00:00")
                        )
                        if updated_at_str
                        else None,
                        "created_at": datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                        if created_at_str
                        else None,
                        "pushed_at": datetime.fromisoformat(
                            pushed_at_str.replace("Z", "+00:00")
                        )
                        if pushed_at_str
                        else None,
                        "open_issues": repo.get("open_issues_count", 0),
                        "language": repo.get("language"),
                        "url": repo.get("html_url"),
                        "topics": repo.get("topics", []),
                        "forks": repo.get("forks_count", 0),
                        "size": repo.get("size"),
                        "archived": repo.get("archived", False),
                        "fork": repo.get("fork", False),
                        "private": repo.get("private", False),
                        "license": repo.get("license", {}).get("key")
                        if repo.get("license")
                        else None,
                    }
                    starred_repos.append(repo_data)

                    # Check if we've reached the limit
                    if limit and len(starred_repos) >= limit:
                        return starred_repos[:limit]

                # Less than max results means last page
                if len(data) < per_page:
                    break

                page += 1
                time.sleep(0.5)  # Be nice to the API

            return starred_repos

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def analyze_repository_activity(self, repo_full_name: str) -> dict:
        """
        Analyze recent activity in a repository.

        Args:
            repo_full_name: Full repository name (e.g., "username/repo")

        Returns:
            Dictionary containing activity metrics
        """
        try:
            self._handle_rate_limit()

            # Split owner and repo name
            owner, repo_name = repo_full_name.split("/", 1)

            # Get repository details
            repo = self.client.get_repo(owner, repo_name)

            # Get recent commits (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            commits = self.client.get_repo_commits(
                owner, repo_name, since=thirty_days_ago
            )
            recent_commits = len(commits)

            # Get open issues and PRs
            open_issues_list = self.client.get_repo_issues(
                owner, repo_name, state="open"
            )
            # Filter out pull requests (GitHub API treats PRs as issues)
            open_issues = len(
                [issue for issue in open_issues_list if "pull_request" not in issue]
            )

            open_prs_list = self.client.get_repo_pulls(owner, repo_name, state="open")
            open_prs = len(open_prs_list)

            # Parse dates
            pushed_at_str = repo.get("pushed_at")
            created_at_str = repo.get("created_at")

            activity_data = {
                "recent_commits": recent_commits,
                "name": repo["full_name"],
                "description": repo.get("description"),
                "open_issues": open_issues,
                "open_pull_requests": open_prs,
                "stargazers": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "last_push": datetime.fromisoformat(
                    pushed_at_str.replace("Z", "+00:00")
                )
                if pushed_at_str
                else None,
                "created_at": datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                if created_at_str
                else None,
                "primary_language": repo.get("language"),
                "topics": repo.get("topics", []),
            }

            return activity_data

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def search_repositories(
        self, query: str, sort: str | None = "stars", limit: int = 10
    ) -> list[dict]:
        """
        Search for repositories matching criteria.

        Args:
            query: Search query string
            sort: How to sort results ("stars", "forks",
                "updated")
            limit: Maximum number of results to return

        Returns:
            List of matching repositories
        """
        try:
            self._handle_rate_limit()

            repositories = self.client.search_repositories(query=query, sort=sort)

            if not repositories:
                return []

            results = []
            for repo in repositories[:limit]:
                updated_at_str = repo.get("updated_at")
                repo_data = {
                    "name": repo["full_name"],
                    "description": repo.get("description"),
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "language": repo.get("language"),
                    "url": repo["html_url"],
                    "updated_at": datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                    if updated_at_str
                    else None,
                    "topics": repo.get("topics", []),
                }
                results.append(repo_data)

            return results

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def get_user_profile(self, username: str | None = None) -> dict:
        """
        Get detailed information about a GitHub user.

        Args:
            username: GitHub username. If None, uses authenticated user.

        Returns:
            Dictionary containing user information
        """
        try:
            self._handle_rate_limit()

            if username:
                user = self.client.get_user(username)
            else:
                user = self.client.get_authenticated_user()

            # Parse dates
            created_at_str = user.get("created_at")
            updated_at_str = user.get("updated_at")

            profile_data = {
                "login": user["login"],
                "name": user.get("name"),
                "bio": user.get("bio"),
                "location": user.get("location"),
                "public_repos": user.get("public_repos", 0),
                "followers": user.get("followers", 0),
                "following": user.get("following", 0),
                "created_at": datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                if created_at_str
                else None,
                "updated_at": datetime.fromisoformat(
                    updated_at_str.replace("Z", "+00:00")
                )
                if updated_at_str
                else None,
                "email": user.get("email"),
            }

            return profile_data

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def check_rate_limit_status(self) -> dict:
        """
        Check the current rate limit status for the configured token.

        Returns:
            Dictionary containing rate limit information for all endpoints
        """
        try:
            rate_limit = self.client.get_rate_limit()

            status = {
                "core": {
                    "limit": rate_limit.core.limit,
                    "remaining": rate_limit.core.remaining,
                    "reset_time": rate_limit.core.reset_time,
                    "reset_timestamp": rate_limit.core.reset_timestamp,
                },
                "search": {
                    "limit": rate_limit.search.limit,
                    "remaining": rate_limit.search.remaining,
                    "reset_time": rate_limit.search.reset_time,
                    "reset_timestamp": rate_limit.search.reset_timestamp,
                },
                "graphql": {
                    "limit": rate_limit.graphql.limit,
                    "remaining": rate_limit.graphql.remaining,
                    "reset_time": rate_limit.graphql.reset_time,
                    "reset_timestamp": rate_limit.graphql.reset_timestamp,
                },
            }

            return status

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def validate_token(self) -> dict:
        """
        Validate the GitHub token and return detailed information about it.

        Returns:
            Dictionary containing token validation status and metadata
        """
        try:
            # Test authentication by getting the authenticated user
            user = self.client.get_authenticated_user()

            # Get rate limit information to understand token capabilities
            rate_limit = self.client.get_rate_limit()

            validation_data = {
                "valid": True,
                "authenticated_user": {
                    "login": user["login"],
                    "name": user.get("name"),
                    "type": user.get("type"),
                    "id": user.get("id"),
                    "public_repos": user.get("public_repos", 0),
                    "followers": user.get("followers", 0),
                    "following": user.get("following", 0),
                },
                "rate_limits": {
                    "core": {
                        "limit": rate_limit.core.limit,
                        "remaining": rate_limit.core.remaining,
                        "reset_time": rate_limit.core.reset_time,
                    },
                    "search": {
                        "limit": rate_limit.search.limit,
                        "remaining": rate_limit.search.remaining,
                        "reset_time": rate_limit.search.reset_time,
                    },
                },
                "token_info": {
                    "can_access_user_data": True,
                    "can_access_rate_limits": True,
                    "note": "Token is valid and can access public GitHub resources",
                },
            }

            return validation_data

        except GitHubAPIError as e:
            # Token is invalid or has insufficient permissions
            error_details = {
                "valid": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }

            # Provide more specific error information based on status code
            if e.status_code:
                if e.status_code == 401:
                    error_details["issue"] = "Invalid token or token has expired"
                elif e.status_code == 403:
                    error_details["issue"] = (
                        "Token lacks required permissions or rate limit exceeded"
                    )
                elif e.status_code == 404:
                    error_details["issue"] = (
                        "Token may be valid but lacks access to requested resources"
                    )
                else:
                    error_details["issue"] = f"HTTP {e.status_code} error occurred"

            return error_details
        except Exception as e:
            # Unexpected error
            return {
                "valid": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "issue": "Unexpected error during token validation",
            }

    def get_repository_labels(self, repo_full_name: str) -> list[dict]:
        """
        Retrieve all labels from a specific repository.

        Args:
            repo_full_name: Full repository name (e.g., "username/repo")

        Returns:
            List of dictionaries containing label information
        """
        try:
            self._handle_rate_limit()

            # Split owner and repo name
            owner, repo_name = repo_full_name.split("/", 1)

            # Get labels
            labels_data = self.client.get_repo_labels(owner, repo_name)
            labels = []

            for label in labels_data:
                label_data = {
                    "name": label["name"],
                    "color": label["color"],
                    "description": label.get("description"),
                    "url": label["url"],
                }
                labels.append(label_data)

            return labels

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def search_repositories_by_topic(
        self, search_params: "RepositorySearchByTopicInput"
    ) -> list[dict]:
        """
        Search for repositories with specific topics and advanced filtering.

        Args:
            search_params: RepositorySearchByTopicInput with search criteria and filters

        Returns:
            List of matching repositories with topic information
        """
        try:
            self._handle_rate_limit()

            # Build search query from parameters
            query = build_repository_search_query(search_params)

            repositories = self.client.search_repositories(
                query=query, sort=search_params.sort
            )

            if not repositories:
                return []

            results = []
            for repo in repositories[: search_params.limit]:
                # Get topics for this repository (should be in response)
                repo_topics = repo.get("topics", [])

                # Parse dates
                updated_at_str = repo.get("updated_at")
                created_at_str = repo.get("created_at")
                pushed_at_str = repo.get("pushed_at")

                repo_data = {
                    "name": repo["full_name"],
                    "description": repo.get("description"),
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "language": repo.get("language"),
                    "url": repo["html_url"],
                    "updated_at": datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                    if updated_at_str
                    else None,
                    "created_at": datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    if created_at_str
                    else None,
                    "pushed_at": datetime.fromisoformat(
                        pushed_at_str.replace("Z", "+00:00")
                    )
                    if pushed_at_str
                    else None,
                    "size": repo.get("size"),
                    "archived": repo.get("archived", False),
                    "fork": repo.get("fork", False),
                    "private": repo.get("private", False),
                    "license": repo.get("license", {}).get("key")
                    if repo.get("license")
                    else None,
                    "topics": repo_topics,
                    "matched_topics": [
                        topic for topic in search_params.topics if topic in repo_topics
                    ],
                    "query_used": query,
                }
                results.append(repo_data)

            return results

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def query_issues(self, query_params: "QueryIssuesInput") -> list[dict]:
        """
        Query issues from a repository with filtering and sorting options.

        Args:
            query_params: QueryIssuesInput with search criteria and filters

        Returns:
            List of dictionaries containing issue information
        """
        try:
            self._handle_rate_limit()

            # Split owner and repo name
            owner, repo_name = query_params.repo_full_name.split("/", 1)

            # Get issues with filters
            issues_list = self.client.get_repo_issues(
                owner=owner,
                repo=repo_name,
                state=query_params.state,
                labels=query_params.labels,
                sort=query_params.sort,
                direction=query_params.direction,
                since=query_params.since,
                per_page=min(100, query_params.limit * 2),
            )

            results = []
            for issue in issues_list:
                # Filter out pull requests (GitHub API treats PRs as issues)
                if "pull_request" in issue:
                    continue

                # Extract label names
                label_names = [label["name"] for label in issue.get("labels", [])]

                # Parse dates
                created_at_str = issue.get("created_at")
                updated_at_str = issue.get("updated_at")

                issue_data = {
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "labels": label_names,
                    "author": issue["user"]["login"] if issue.get("user") else None,
                    "created_at": datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    if created_at_str
                    else None,
                    "updated_at": datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                    if updated_at_str
                    else None,
                    "url": issue["html_url"],
                    "comments_count": issue.get("comments", 0),
                    "body": issue.get("body", "")[:500] if issue.get("body") else None,
                }
                results.append(issue_data)

                # Stop once we have enough actual issues (not PRs)
                if len(results) >= query_params.limit:
                    break

            return results

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def analyze_commit_hotspots(self, hotspot_params: "CommitHotspotInput") -> dict:
        """
        Analyze maintenance hotspots by examining commit history.

        Identifies files that change frequently, which may indicate architectural
        issues, complexity, or areas needing refactoring.

        Args:
            hotspot_params: CommitHotspotInput with analysis parameters

        Returns:
            Dictionary containing hotspot analysis results
        """
        import base64

        from .churn_strategies import (
            ReworkRateStrategy,
            TotalActivityChurnStrategy,
        )
        from .hotspot_tracker import FileChangeTracker

        try:
            self._handle_rate_limit()

            # Split owner and repo name
            owner, repo_name = hotspot_params.repo_full_name.split("/", 1)

            # Calculate time window
            date_range_end = datetime.now()
            date_range_start = date_range_end - timedelta(days=hotspot_params.days)

            # Select churn calculation strategy
            strategy_map = {
                "activity": TotalActivityChurnStrategy(),
                "rework": ReworkRateStrategy(),
            }
            # Default to activity strategy for backward compatibility with
            # 'simple' and 'author' which were removed
            strategy = strategy_map.get(
                hotspot_params.strategy, TotalActivityChurnStrategy()
            )

            # Initialize file change tracker with selected strategy
            tracker = FileChangeTracker(strategy=strategy)

            # Get baseline LOC if using activity churn strategy
            baseline_loc_map: dict[str, int] = {}
            if isinstance(strategy, TotalActivityChurnStrategy):
                try:
                    # Get repository tree at the start of analysis period
                    # Find the commit closest to date_range_start
                    commits_at_start = self.client.get_repo_commits(
                        owner,
                        repo_name,
                        until=date_range_start,
                        per_page=1,
                        max_pages=1,
                    )
                    if commits_at_start:
                        baseline_commit = commits_at_start[0]
                        tree = self.client.get_git_tree(
                            owner, repo_name, baseline_commit["sha"], recursive=True
                        )

                        # Count LOC for each file
                        for item in tree.get("tree", []):
                            if item["type"] == "blob":  # It's a file, not a directory
                                try:
                                    # Fetch file contents
                                    blob = self.client.get_git_blob(
                                        owner, repo_name, item["sha"]
                                    )
                                    if blob.get("encoding") == "base64":
                                        # Decode and count lines
                                        content = base64.b64decode(
                                            blob["content"]
                                        ).decode("utf-8", errors="ignore")
                                        loc = len(content.splitlines())
                                        baseline_loc_map[item["path"]] = loc
                                except Exception:
                                    # Skip files we can't read
                                    continue

                except Exception as baseline_error:
                    print(f"Warning: Could not fetch baseline LOC: {baseline_error}")

            # Get commits with optional path filter
            # Calculate max pages based on max_commits
            max_pages = (hotspot_params.max_commits + 99) // 100  # Round up

            commits = self.client.get_repo_commits(
                owner=owner,
                repo=repo_name,
                since=date_range_start,
                path=hotspot_params.path,
                per_page=100,
                max_pages=max_pages,
            )

            commits_analyzed = 0

            # Process commits up to max_commits limit
            for commit_summary in commits[: hotspot_params.max_commits]:
                self._handle_rate_limit()

                # Get full commit details with file changes
                try:
                    commit = self.client.get_commit(
                        owner, repo_name, commit_summary["sha"]
                    )

                    # Access commit files
                    for file in commit.get("files", []):
                        # Parse commit date
                        commit_date_str = commit["commit"]["author"]["date"]
                        commit_date = datetime.fromisoformat(
                            commit_date_str.replace("Z", "+00:00")
                        )

                        # Record the file change with commit SHA
                        tracker.record_file_change(
                            file_path=file["filename"],
                            additions=file.get("additions", 0),
                            deletions=file.get("deletions", 0),
                            author_login=commit["author"]["login"]
                            if commit.get("author")
                            else None,
                            commit_date=commit_date,
                            commit_sha=commit["sha"],
                        )

                        # Set baseline LOC if available
                        if file["filename"] in baseline_loc_map:
                            tracker.set_baseline_loc(
                                file["filename"], baseline_loc_map[file["filename"]]
                            )

                except Exception as file_error:
                    # Log but continue if we can't access files for a commit
                    error_msg = (
                        f"Warning: Could not access files for "
                        f"commit {commit_summary['sha']}: {file_error}"
                    )
                    print(error_msg)
                    continue

                commits_analyzed += 1
                time.sleep(0.1)  # Small delay to be nice to API

            # Get hotspots from tracker
            hotspots = tracker.get_hotspots(hotspot_params.min_changes)

            # Build result
            result = {
                "hotspots": [h.model_dump() for h in hotspots],
                "analysis_period_days": hotspot_params.days,
                "total_commits_analyzed": commits_analyzed,
                "total_files_changed": tracker.total_files_changed,
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "path_filter": hotspot_params.path,
                "strategy": hotspot_params.strategy,
            }

            return result

        except GitHubAPIError as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def close(self) -> None:
        """Close the GitHub connection."""
        self.client.close()
