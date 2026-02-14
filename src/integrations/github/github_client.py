"""
GitHub API Client

This module provides a lightweight GitHub API client.
It uses direct HTTP requests to interact with the GitHub REST API v3.

Features:
- Token-based authentication
- Rate limit handling
- Pagination support
- Comprehensive error handling
- Type-safe responses with Pydantic models
"""

import time
from datetime import datetime
from typing import Any

import requests
from pydantic import BaseModel


class GitHubAPIError(Exception):
    """Exception raised for GitHub API errors."""

    def __init__(
        self, message: str, status_code: int | None = None, response: Any = None
    ):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class RateLimitInfo(BaseModel):
    """Rate limit information for a specific resource."""

    limit: int
    remaining: int
    reset_timestamp: float
    reset_time: str


class RateLimitStatus(BaseModel):
    """Complete rate limit status for all resources."""

    core: RateLimitInfo
    search: RateLimitInfo
    graphql: RateLimitInfo


class GitHubClient:
    """
    GitHub API client for making authenticated requests.

    This client provides methods for interacting with the GitHub REST API v3.
    It handles authentication, rate limiting, pagination, and error responses.
    """

    BASE_URL = "https://api.github.com"
    API_VERSION = "2022-11-28"

    def __init__(self, token: str):
        """
        Initialize the GitHub API client.

        Args:
            token: GitHub personal access token for authentication
        """
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": self.API_VERSION,
            }
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """
        Make an HTTP request to the GitHub API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/user")
            params: Query parameters
            data: Request body data
            custom_headers: Additional headers to include

        Returns:
            Response object

        Raises:
            GitHubAPIError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = custom_headers or {}

        try:
            response = self.session.request(
                method=method, url=url, params=params, json=data, headers=headers
            )

            # Handle rate limiting
            if response.status_code == 403:
                if "rate limit exceeded" in response.text.lower():
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    if reset_time:
                        wait_time = reset_time - time.time()
                        if wait_time > 0:
                            time.sleep(wait_time)
                            # Retry the request
                            return self._make_request(
                                method, endpoint, params, data, custom_headers
                            )

            # Raise for HTTP errors
            if not response.ok:
                error_msg = f"GitHub API error: {response.status_code}"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg = f"{error_msg} - {error_data['message']}"
                except Exception:
                    error_msg = f"{error_msg} - {response.text[:200]}"

                raise GitHubAPIError(error_msg, response.status_code, response)

            return response

        except requests.RequestException as e:
            raise GitHubAPIError(f"Request failed: {str(e)}") from e

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
    ) -> Any:
        """
        Make a GET request to the GitHub API.

        Args:
            endpoint: API endpoint
            params: Query parameters
            custom_headers: Additional headers

        Returns:
            JSON response data
        """
        response = self._make_request(
            "GET", endpoint, params, custom_headers=custom_headers
        )
        return response.json()

    def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int | None = None,
    ) -> list[Any]:
        """
        Get all pages of results from a paginated endpoint.

        Args:
            endpoint: API endpoint
            params: Query parameters
            per_page: Results per page (max 100)
            max_pages: Maximum number of pages to fetch (None for all)

        Returns:
            List of all items from all pages
        """
        params = params or {}
        params["per_page"] = min(per_page, 100)
        all_items = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            params["page"] = page
            items = self.get(endpoint, params)

            if not items:
                break

            # Handle both list and dict responses
            if isinstance(items, list):
                all_items.extend(items)
                if len(items) < params["per_page"]:
                    break
            elif isinstance(items, dict) and "items" in items:
                # Search API responses
                all_items.extend(items["items"])
                if len(items["items"]) < params["per_page"]:
                    break
            else:
                # Single item response
                all_items.append(items)
                break

            page += 1
            time.sleep(0.1)  # Be nice to the API

        return all_items

    def get_rate_limit(self) -> RateLimitStatus:
        """
        Get current rate limit status for all resources.

        Returns:
            RateLimitStatus object with rate limit information
        """
        data = self.get("/rate_limit")
        resources = data["resources"]

        def parse_resource(res_data: dict[str, Any]) -> RateLimitInfo:
            reset_ts = res_data["reset"]
            return RateLimitInfo(
                limit=res_data["limit"],
                remaining=res_data["remaining"],
                reset_timestamp=reset_ts,
                reset_time=datetime.fromtimestamp(reset_ts).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),
            )

        return RateLimitStatus(
            core=parse_resource(resources["core"]),
            search=parse_resource(resources["search"]),
            graphql=parse_resource(resources["graphql"]),
        )

    def check_rate_limit_and_wait(self) -> None:
        """Check rate limit and sleep if necessary."""
        rate_limit = self.get_rate_limit()
        if rate_limit.core.remaining < 10:
            reset_time = rate_limit.core.reset_timestamp - time.time()
            if reset_time > 0:
                time.sleep(reset_time)

    def get_authenticated_user(self) -> dict[str, Any]:
        """
        Get the authenticated user's profile.

        Returns:
            User profile data
        """
        return self.get("/user")

    def get_user(self, username: str) -> dict[str, Any]:
        """
        Get a user's public profile.

        Args:
            username: GitHub username

        Returns:
            User profile data
        """
        return self.get(f"/users/{username}")

    def get_starred_repos(
        self,
        username: str | None = None,
        sort: str | None = None,
        direction: str = "desc",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Get starred repositories for a user.

        Args:
            username: GitHub username (None for authenticated user)
            sort: Sort by 'created' or 'updated'
            direction: Sort direction ('asc' or 'desc')
            per_page: Results per page

        Returns:
            List of repository data
        """
        if username:
            endpoint = f"/users/{username}/starred"
        else:
            endpoint = "/user/starred"

        params: dict[str, Any] = {}
        if sort:
            params["sort"] = sort
            params["direction"] = direction

        # Need to use custom header to get topics
        custom_headers = {"Accept": "application/vnd.github.mercy-preview+json"}

        return self.get_paginated(
            endpoint, params, per_page=per_page, custom_headers=custom_headers
        )

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """
        Get repository details.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository data
        """
        # Use custom header to get topics
        custom_headers = {"Accept": "application/vnd.github.mercy-preview+json"}
        return self.get(f"/repos/{owner}/{repo}", custom_headers=custom_headers)

    def get_repo_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
        until: datetime | None = None,
        path: str | None = None,
        per_page: int = 100,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get commits for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            since: Only commits after this date
            until: Only commits before this date
            path: Only commits touching this path
            per_page: Results per page
            max_pages: Maximum number of pages to fetch

        Returns:
            List of commit data
        """
        params: dict[str, Any] = {}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if path:
            params["path"] = path

        return self.get_paginated(
            f"/repos/{owner}/{repo}/commits", params, per_page, max_pages
        )

    def get_commit(self, owner: str, repo: str, sha: str) -> dict[str, Any]:
        """
        Get a single commit with file details.

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA

        Returns:
            Commit data with files
        """
        return self.get(f"/repos/{owner}/{repo}/commits/{sha}")

    def get_repo_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: list[str] | None = None,
        sort: str = "created",
        direction: str = "desc",
        since: datetime | None = None,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Get issues for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state ('open', 'closed', 'all')
            labels: Filter by labels
            sort: Sort by ('created', 'updated', 'comments')
            direction: Sort direction ('asc', 'desc')
            since: Only issues updated after this date
            per_page: Results per page

        Returns:
            List of issue data
        """
        params: dict[str, Any] = {"state": state, "sort": sort, "direction": direction}
        if labels:
            params["labels"] = ",".join(labels)
        if since:
            params["since"] = since.isoformat()

        return self.get_paginated(f"/repos/{owner}/{repo}/issues", params, per_page)

    def get_repo_pulls(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Get pull requests for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state ('open', 'closed', 'all')
            per_page: Results per page

        Returns:
            List of pull request data
        """
        params = {"state": state}
        return self.get_paginated(f"/repos/{owner}/{repo}/pulls", params, per_page)

    def search_repositories(
        self, query: str, sort: str | None = None, per_page: int = 30
    ) -> list[dict[str, Any]]:
        """
        Search for repositories.

        Args:
            query: Search query
            sort: Sort by ('stars', 'forks', 'updated')
            per_page: Results per page

        Returns:
            List of repository data
        """
        params: dict[str, Any] = {"q": query}
        if sort:
            params["sort"] = sort

        # Use custom header to get topics
        custom_headers = {"Accept": "application/vnd.github.mercy-preview+json"}

        response = self.get(
            "/search/repositories", params, custom_headers=custom_headers
        )
        return response.get("items", [])

    def get_repo_labels(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """
        Get labels for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of label data
        """
        return self.get_paginated(f"/repos/{owner}/{repo}/labels")

    def get_git_tree(
        self, owner: str, repo: str, tree_sha: str, recursive: bool = False
    ) -> dict[str, Any]:
        """
        Get a Git tree.

        Args:
            owner: Repository owner
            repo: Repository name
            tree_sha: Tree SHA
            recursive: Whether to get the tree recursively

        Returns:
            Tree data
        """
        params = {}
        if recursive:
            params["recursive"] = "1"
        return self.get(f"/repos/{owner}/{repo}/git/trees/{tree_sha}", params)

    def get_git_blob(self, owner: str, repo: str, blob_sha: str) -> dict[str, Any]:
        """
        Get a Git blob (file content).

        Args:
            owner: Repository owner
            repo: Repository name
            blob_sha: Blob SHA

        Returns:
            Blob data
        """
        return self.get(f"/repos/{owner}/{repo}/git/blobs/{blob_sha}")

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self) -> "GitHubClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
