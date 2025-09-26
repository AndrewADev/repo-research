"""
GitHub API Tool Methods for AI Agents

This module provides a collection of functions for interacting with GitHub's API,
specifically designed to be used as tools by an AI agent. Each function is self-contained
and handles its own error checking and rate limiting.

Requirements:
    - PyGithub
    - python-dotenv
"""

from github import Github, Auth, GithubException, RateLimitExceededException
from typing import List, Dict, Optional
from datetime import datetime
import time
import os
from dotenv import load_dotenv


class GitHubTools:
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub tools with authentication.

        Args:
            token: GitHub personal access token. If None, will try to load from environment.
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
        self, username: Optional[str] = None, sort_by: str = "stars"
    ) -> List[Dict]:
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

        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def analyze_repository_activity(self, repo_full_name: str) -> Dict:
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

        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def search_repositories(
        self, query: str, sort: Optional[str] = "stars", limit: int = 10
    ) -> List[Dict]:
        """
        Search for repositories matching criteria.

        Args:
            query: Search query string
            sort: How to sort results ("stars", "forks", "updated")
            limit: Maximum number of results to return

        Returns:
            List of matching repositories
        """
        try:
            self._handle_rate_limit()

            results = []
            repositories = self.github.search_repositories(query=query, sort=sort)

            for repo in repositories[:limit]:
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

        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def get_user_profile(self, username: Optional[str] = None) -> Dict:
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

        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def check_rate_limit_status(self) -> Dict:
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
            raise Exception(f"GitHub API error: {str(e)}")

    def validate_token(self) -> Dict:
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

    def close(self) -> None:
        """Close the GitHub connection."""
        self.github.close()
