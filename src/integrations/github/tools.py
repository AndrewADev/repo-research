"""
GitHub API Tool Methods for AI Agents

This module provides a collection of functions for interacting with GitHub's API,
specifically designed to be used as tools by an AI agent. Each function is
self-contained and handles its own error checking and rate limiting.

Requirements:
    - PyGithub
    - python-dotenv
"""

import os
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from github import Auth, Github, GithubException
from github.GithubObject import NotSet

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

        self.auth = Auth.Token(token)
        self.github = Github(auth=self.auth)

    def _handle_rate_limit(self) -> None:
        """Check rate limit and sleep if necessary."""
        rate_limit = self.github.get_rate_limit()
        if rate_limit.resources.core.remaining < 10:
            reset_time = rate_limit.resources.core.reset.timestamp() - time.time()
            if reset_time > 0:
                time.sleep(reset_time)

    def get_starred_repositories(
        self, username: str | None = None, sort_by: str = "stars"
    ) -> list[dict]:
        """
        Retrieve and sort starred repositories for a user.

        Args:
            username: GitHub username. If None, uses authenticated user.
            sort_by: How to sort results. Options: "stars", "recent", "issues"

        Returns:
            List of dictionaries containing repository information
        """
        try:
            self._handle_rate_limit()

            if username:
                user = self.github.get_user(username)
            else:
                user = self.github.get_user()

            starred_repos = []
            page = 0

            while True:
                repos_page = user.get_starred().get_page(page)
                if not repos_page:
                    break

                for repo in repos_page:
                    repo_data = {
                        "name": repo.full_name,
                        "description": repo.description,
                        "stars": repo.stargazers_count,
                        "updated_at": repo.updated_at,
                        "open_issues": repo.open_issues_count,
                        "language": repo.language,
                        "url": repo.html_url,
                    }
                    starred_repos.append(repo_data)

                page += 1
                time.sleep(0.5)  # Be nice to the API

            # Sort the results
            if sort_by == "stars":
                starred_repos.sort(key=lambda x: x["stars"], reverse=True)
            elif sort_by == "recent":
                starred_repos.sort(key=lambda x: x["updated_at"], reverse=True)
            elif sort_by == "issues":
                starred_repos.sort(key=lambda x: x["open_issues"], reverse=True)

            return starred_repos

        except GithubException as e:
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

            repo = self.github.get_repo(repo_full_name)

            # Get recent commits (last 30 days)
            recent_commits = 0
            thirty_days_ago = datetime.now().timestamp() - (30 * 24 * 60 * 60)

            for commit in repo.get_commits():
                if commit.commit.author.date.timestamp() < thirty_days_ago:
                    break
                recent_commits += 1

            # Get open issues and PRs
            open_issues = repo.get_issues(state="open").totalCount
            open_prs = repo.get_pulls(state="open").totalCount

            activity_data = {
                "recent_commits": recent_commits,
                "name": repo.full_name,
                "description": repo.description,
                "open_issues": open_issues,
                "open_pull_requests": open_prs,
                "stargazers": repo.stargazers_count,
                "forks": repo.forks_count,
                "last_push": repo.pushed_at,
                "created_at": repo.created_at,
                "primary_language": repo.language,
                "topics": repo.topics,
            }

            return activity_data

        except GithubException as e:
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

            results = []
            repositories_pages = self.github.search_repositories(query=query, sort=sort)

            if repositories_pages.totalCount < 1:
                return results

            for repo in repositories_pages[:limit]:
                repo_data = {
                    "name": repo.full_name,
                    "description": repo.description,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "language": repo.language,
                    "url": repo.html_url,
                    "updated_at": repo.updated_at,
                    "topics": repo.topics,
                }
                results.append(repo_data)

            return results

        except GithubException as e:
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
                user = self.github.get_user(username)
            else:
                user = self.github.get_user()

            profile_data = {
                "login": user.login,
                "name": user.name,
                "bio": user.bio,
                "location": user.location,
                "public_repos": user.public_repos,
                "followers": user.followers,
                "following": user.following,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "email": user.email,
            }

            return profile_data

        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def check_rate_limit_status(self) -> dict:
        """
        Check the current rate limit status for the configured token.

        Returns:
            Dictionary containing rate limit information for all endpoints
        """
        try:
            rate_limit = self.github.get_rate_limit()

            # Core rate limit (most API calls)
            core = rate_limit.resources.core

            # Search rate limit (search API calls)
            search = rate_limit.resources.search

            # GraphQL rate limit
            graphql = rate_limit.resources.graphql

            status = {
                "core": {
                    "limit": core.limit,
                    "remaining": core.remaining,
                    "reset_time": core.reset.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "reset_timestamp": core.reset.timestamp(),
                },
                "search": {
                    "limit": search.limit,
                    "remaining": search.remaining,
                    "reset_time": search.reset.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "reset_timestamp": search.reset.timestamp(),
                },
                "graphql": {
                    "limit": graphql.limit,
                    "remaining": graphql.remaining,
                    "reset_time": graphql.reset.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "reset_timestamp": graphql.reset.timestamp(),
                },
            }

            return status

        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def validate_token(self) -> dict:
        """
        Validate the GitHub token and return detailed information about it.

        Returns:
            Dictionary containing token validation status and metadata
        """
        try:
            # Test authentication by getting the authenticated user
            user = self.github.get_user()

            # Get rate limit information to understand token capabilities
            rate_limit = self.github.get_rate_limit()

            # Attempt to get token metadata (scopes, etc.)
            # Note: The GitHub API doesn't expose all token details via REST API
            # but we can infer some information from successful operations

            validation_data = {
                "valid": True,
                "authenticated_user": {
                    "login": user.login,
                    "name": user.name,
                    "type": user.type,
                    "id": user.id,
                    "public_repos": user.public_repos,
                    "followers": user.followers,
                    "following": user.following,
                },
                "rate_limits": {
                    "core": {
                        "limit": rate_limit.resources.core.limit,
                        "remaining": rate_limit.resources.core.remaining,
                        "reset_time": rate_limit.resources.core.reset.strftime(
                            "%Y-%m-%d %H:%M:%S UTC"
                        ),
                    },
                    "search": {
                        "limit": rate_limit.resources.search.limit,
                        "remaining": rate_limit.resources.search.remaining,
                        "reset_time": rate_limit.resources.search.reset.strftime(
                            "%Y-%m-%d %H:%M:%S UTC"
                        ),
                    },
                },
                "token_info": {
                    "can_access_user_data": True,
                    "can_access_rate_limits": True,
                    "note": "Token is valid and can access public GitHub resources",
                },
            }

            return validation_data

        except GithubException as e:
            # Token is invalid or has insufficient permissions
            error_details = {
                "valid": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }

            # Provide more specific error information based on status code
            if hasattr(e, "status"):
                if e.status == 401:
                    error_details["issue"] = "Invalid token or token has expired"
                elif e.status == 403:
                    error_details["issue"] = (
                        "Token lacks required permissions or rate limit exceeded"
                    )
                elif e.status == 404:
                    error_details["issue"] = (
                        "Token may be valid but lacks access to requested resources"
                    )
                else:
                    error_details["issue"] = f"HTTP {e.status} error occurred"

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

            repo = self.github.get_repo(repo_full_name)
            labels = []

            for label in repo.get_labels():
                label_data = {
                    "name": label.name,
                    "color": label.color,
                    "description": label.description,
                    "url": label.url,
                }
                labels.append(label_data)

            return labels

        except GithubException as e:
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

            results = []
            repositories_pages = self.github.search_repositories(
                query=query, sort=search_params.sort
            )

            if repositories_pages.totalCount < 1:
                return results

            for repo in repositories_pages[: search_params.limit]:
                # Get topics for this repository
                repo_topics = []
                try:
                    repo_topics = repo.get_topics()
                except Exception:
                    # If we can't get topics, continue without them
                    pass

                repo_data = {
                    "name": repo.full_name,
                    "description": repo.description,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "language": repo.language,
                    "url": repo.html_url,
                    "updated_at": repo.updated_at,
                    "created_at": repo.created_at,
                    "pushed_at": repo.pushed_at,
                    "size": repo.size,
                    "archived": repo.archived,
                    "fork": repo.fork,
                    "private": repo.private,
                    "license": repo.license.key if repo.license else None,
                    "topics": repo_topics,
                    "matched_topics": [
                        topic for topic in search_params.topics if topic in repo_topics
                    ],
                    "query_used": query,
                }
                results.append(repo_data)

            return results

        except GithubException as e:
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

            repo = self.github.get_repo(query_params.repo_full_name)

            # Get issues with filters
            issues_paginated = repo.get_issues(
                state=query_params.state,
                labels=query_params.labels or [],
                sort=query_params.sort,
                direction=query_params.direction,
                since=query_params.since if query_params.since else NotSet,
            )

            results = []
            # Use slice notation for lazy pagination - only fetch what we need
            for issue in issues_paginated[: query_params.limit * 2]:
                # Filter out pull requests (GitHub API treats PRs as issues)
                if issue.pull_request is not None:
                    continue

                # Extract label names
                label_names = [label.name for label in issue.labels]

                issue_data = {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "labels": label_names,
                    "author": issue.user.login if issue.user else None,
                    "created_at": issue.created_at,
                    "updated_at": issue.updated_at,
                    "url": issue.html_url,
                    "comments_count": issue.comments,
                    "body": issue.body[:500] if issue.body else None,
                }
                results.append(issue_data)

                # Stop once we have enough actual issues (not PRs)
                if len(results) >= query_params.limit:
                    break

            return results

        except GithubException as e:
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
        from .churn_strategies import (
            ReworkRateStrategy,
            TotalActivityChurnStrategy,
        )
        from .hotspot_tracker import FileChangeTracker

        try:
            self._handle_rate_limit()

            repo = self.github.get_repo(hotspot_params.repo_full_name)

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
                    commits_at_start = repo.get_commits(until=date_range_start)
                    try:
                        baseline_commit = commits_at_start[0]
                        tree = repo.get_git_tree(baseline_commit.sha, recursive=True)

                        # Count LOC for each file
                        for item in tree.tree:
                            if item.type == "blob":  # It's a file, not a directory
                                try:
                                    # Fetch file contents
                                    blob = repo.get_git_blob(item.sha)
                                    if blob.encoding == "base64":
                                        # Decode and count lines
                                        import base64

                                        content = base64.b64decode(blob.content).decode(
                                            "utf-8", errors="ignore"
                                        )
                                        loc = len(content.splitlines())
                                        baseline_loc_map[item.path] = loc
                                except Exception:
                                    # Skip files we can't read
                                    continue

                    except IndexError:
                        # No commits at baseline, use empty baseline
                        pass

                except Exception as baseline_error:
                    print(f"Warning: Could not fetch baseline LOC: {baseline_error}")

            # Get commits with optional path filter
            if hotspot_params.path:
                commits = repo.get_commits(
                    since=date_range_start, path=hotspot_params.path
                )
            else:
                commits = repo.get_commits(since=date_range_start)

            commits_analyzed = 0

            # Process commits up to max_commits limit
            for commit in commits:
                if commits_analyzed >= hotspot_params.max_commits:
                    break

                self._handle_rate_limit()

                # Access commit files
                try:
                    for file in commit.files:
                        # Record the file change with commit SHA
                        tracker.record_file_change(
                            file_path=file.filename,
                            additions=file.additions,
                            deletions=file.deletions,
                            author_login=commit.author.login if commit.author else None,
                            commit_date=commit.commit.author.date,
                            commit_sha=commit.sha,
                        )

                        # Set baseline LOC if available
                        if file.filename in baseline_loc_map:
                            tracker.set_baseline_loc(
                                file.filename, baseline_loc_map[file.filename]
                            )

                except Exception as file_error:
                    # Log but continue if we can't access files for a commit
                    error_msg = (
                        f"Warning: Could not access files for "
                        f"commit {commit.sha}: {file_error}"
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

        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}") from e

    def close(self) -> None:
        """Close the GitHub connection."""
        self.github.close()
