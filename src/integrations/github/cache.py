"""
GitHub API response cache backed by diskcache.

Provides a TTL policy table keyed by URL path and a thin wrapper around
``diskcache.Cache``. Designed to be composed with :class:`GitHubClient` via
:class:`CachedGitHubClient` — this module never talks to the network.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Final, Literal

import diskcache  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

# TTLs (seconds). ``None`` means "no expiry — evict only via LRU under size_limit".
TTL_IMMUTABLE: Final[int | None] = None
TTL_REPO_METADATA: Final[int] = 6 * 60 * 60
TTL_STARRED: Final[int] = 60 * 60
TTL_ISSUES_PULLS: Final[int] = 15 * 60
TTL_ACTIVITY: Final[int] = 5 * 60

NO_CACHE: Final[Literal["no-cache"]] = "no-cache"
TTLDecision = int | None | Literal["no-cache"]


# Allow transparent cache skip without forcing knowledge
# of the cache upon all signatures.
_skip_cache: ContextVar[bool] = ContextVar("github_cache_skip_cache", default=False)


@contextmanager
def no_cache() -> Iterator[None]:
    """Bypass the cache for any reads made within this context.

    Composes through pagination and through any depth of helper calls,
    because the check happens inside :meth:`CachedGitHubClient.get`.

    Example::

        with no_cache():
            commits = client.get_repo_commits(owner, repo, since=...)
    """
    token = _skip_cache.set(True)
    try:
        yield
    finally:
        _skip_cache.reset(token)


def is_cache_bypassed() -> bool:
    """Return ``True`` when the current context is inside :func:`no_cache`."""
    return _skip_cache.get()


class _Miss:
    """Sentinel returned by ``GitHubCache.get`` on a miss."""


MISS: Final[_Miss] = _Miss()


class CachePolicy(BaseModel):
    """A single URL-pattern → TTL rule."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    pattern: re.Pattern[str]
    ttl: int | None | Literal["no-cache"] = Field(
        description="Seconds, None (LRU-only), or 'no-cache' to bypass."
    )


# Order matters — first match wins. SHA-shaped entries precede ref-shaped ones.
_SHA_TAIL = r"[0-9a-f]{7,40}"

DEFAULT_POLICIES: Final[list[CachePolicy]] = [
    # Never cache the rate limit endpoint.
    CachePolicy(pattern=re.compile(r"^/rate_limit$"), ttl=NO_CACHE),
    # SHA-addressed, immutable.
    CachePolicy(
        pattern=re.compile(rf"^/repos/[^/]+/[^/]+/commits/{_SHA_TAIL}$"),
        ttl=TTL_IMMUTABLE,
    ),
    CachePolicy(
        pattern=re.compile(rf"^/repos/[^/]+/[^/]+/git/blobs/{_SHA_TAIL}$"),
        ttl=TTL_IMMUTABLE,
    ),
    CachePolicy(
        pattern=re.compile(rf"^/repos/[^/]+/[^/]+/git/trees/{_SHA_TAIL}$"),
        ttl=TTL_IMMUTABLE,
    ),
    # Branch/ref-addressed tree — mutable, treat as activity.
    CachePolicy(
        pattern=re.compile(r"^/repos/[^/]+/[^/]+/git/trees/"),
        ttl=TTL_ACTIVITY,
    ),
    # Activity: recent commits, repo search.
    CachePolicy(
        pattern=re.compile(r"^/repos/[^/]+/[^/]+/commits$"),
        ttl=TTL_ACTIVITY,
    ),
    CachePolicy(pattern=re.compile(r"^/search/repositories$"), ttl=TTL_ACTIVITY),
    # Issues / PRs — slightly longer.
    CachePolicy(
        pattern=re.compile(r"^/repos/[^/]+/[^/]+/issues"), ttl=TTL_ISSUES_PULLS
    ),
    CachePolicy(pattern=re.compile(r"^/repos/[^/]+/[^/]+/pulls"), ttl=TTL_ISSUES_PULLS),
    # Repo / user metadata — hours.
    CachePolicy(
        pattern=re.compile(r"^/repos/[^/]+/[^/]+/labels$"), ttl=TTL_REPO_METADATA
    ),
    CachePolicy(pattern=re.compile(r"^/repos/[^/]+/[^/]+$"), ttl=TTL_REPO_METADATA),
    # Starred — an hour.
    CachePolicy(pattern=re.compile(r"^/user/starred$"), ttl=TTL_STARRED),
    CachePolicy(pattern=re.compile(r"^/users/[^/]+/starred$"), ttl=TTL_STARRED),
    # User profile.
    CachePolicy(pattern=re.compile(r"^/users/[^/]+$"), ttl=TTL_REPO_METADATA),
    CachePolicy(pattern=re.compile(r"^/user$"), ttl=TTL_REPO_METADATA),
]


def default_cache_dir() -> Path:
    """Default on-disk cache location, matching the conversations DB pattern."""
    from repo_research.storage_paths import storage_root

    return storage_root() / "cache"


def hash_token(token: str) -> str:
    """8-char SHA-256 prefix.

    Isolates cache entries across tokens without storing the token itself.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


class GitHubCache:
    """Thin TTL-aware wrapper around ``diskcache.Cache``.

    The cache is process-shared on disk; opening the same path from multiple
    processes is safe (diskcache uses SQLite under the hood).
    """

    def __init__(
        self,
        path: Path | None = None,
        size_limit: int = 512 * 1024 * 1024,
        policies: list[CachePolicy] | None = None,
    ) -> None:
        self._path = path or default_cache_dir()
        self._path.mkdir(parents=True, exist_ok=True)
        self._cache: diskcache.Cache = diskcache.Cache(
            str(self._path),
            size_limit=size_limit,
            eviction_policy="least-recently-used",
        )
        self._policies: list[CachePolicy] = policies or DEFAULT_POLICIES

    def lookup_ttl(self, endpoint: str) -> TTLDecision:
        """Return the TTL for *endpoint*, or :data:`NO_CACHE` if it shouldn't be cached.

        Unmatched endpoints are conservatively treated as ``NO_CACHE``.
        """
        for policy in self._policies:
            if policy.pattern.match(endpoint):
                return policy.ttl
        return NO_CACHE

    @staticmethod
    def _make_key(
        endpoint: str,
        params: dict[str, Any] | None,
        token_hash: str,
        custom_headers: dict[str, str] | None,
    ) -> str:
        sorted_params = sorted((params or {}).items())
        # Custom headers (notably ``Accept``) negotiate response shape — a blob
        # fetched as raw bytes is not the same entity as a blob fetched as
        # JSON. Include them in the key so different shapes can coexist.
        sorted_headers = sorted((custom_headers or {}).items())
        return f"{token_hash}|{endpoint}?{sorted_params}|h={sorted_headers}"

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None,
        token_hash: str,
        custom_headers: dict[str, str] | None = None,
    ) -> Any | _Miss:
        """Return the cached value or :data:`MISS` if absent/expired."""
        key = self._make_key(endpoint, params, token_hash, custom_headers)
        return self._cache.get(key, default=MISS)

    def set(
        self,
        endpoint: str,
        params: dict[str, Any] | None,
        token_hash: str,
        value: Any,
        ttl: int | None,
        custom_headers: dict[str, str] | None = None,
    ) -> None:
        """Store *value* with the given TTL (``None`` = no expiry)."""
        key = self._make_key(endpoint, params, token_hash, custom_headers)
        self._cache.set(key, value, expire=ttl)

    def clear(self) -> None:
        self._cache.clear()

    def close(self) -> None:
        self._cache.close()
