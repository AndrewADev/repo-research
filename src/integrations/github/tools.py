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
from datetime import datetime
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from github import Auth, Github, GithubException

if TYPE_CHECKING:
    from tools.github_models import RepositorySearchByTopicInput


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
                "open_issues": open_issues,
                "open_pull_requests": open_prs,
                "stargazers": repo.stargazers_count,
                "forks": repo.forks_count,
                "last_push": repo.pushed_at,
                "created_at": repo.created_at,
                "primary_language": repo.language,
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

    def _build_repository_search_query(
        self, search_params: "RepositorySearchByTopicInput"
    ) -> str:
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
        if (
            search_params.size_min_kb is not None
            and search_params.size_max_kb is not None
        ):
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
            query = self._build_repository_search_query(search_params)

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

    def close(self) -> None:
        """Close the GitHub connection."""
        self.github.close()
