"""
Caching decorator over :class:`GitHubClient`.

Wraps the base client with a disk-backed response cache that applies different
TTLs per endpoint volatility. Callers who need a fresh read scope the bypass
with :func:`integrations.github.cache.no_cache`, which composes through
paginated fetches and any depth of helper calls — the base
:class:`GitHubClient` stays unaware of caching entirely.
"""

from __future__ import annotations

import os
from typing import Any

from .cache import (
    MISS,
    NO_CACHE,
    GitHubCache,
    hash_token,
    is_cache_bypassed,
)
from .github_client import GitHubClient

_ENV_DISABLE: str = "GITHUB_AGENT_CACHE_DISABLE"


def _cache_disabled_by_env() -> bool:
    value = os.environ.get(_ENV_DISABLE, "").strip().lower()
    return value in {"1", "true"}


class CachedGitHubClient(GitHubClient):
    """A :class:`GitHubClient` that consults a :class:`GitHubCache` before calling out.

    Pagination loops in the base class call ``self.get`` and therefore inherit
    caching at per-page granularity for free. To bypass caching for a specific
    scope (including a paginated fetch), wrap the calls in
    :func:`integrations.github.cache.no_cache`.
    """

    def __init__(
        self,
        token: str,
        cache: GitHubCache | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(token)
        self._cache_enabled: bool = enabled and not _cache_disabled_by_env()
        self._cache: GitHubCache = cache if cache is not None else GitHubCache()
        self._token_hash: str = hash_token(token)

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        custom_headers: dict[str, str] | None = None,
    ) -> Any:
        if not self._cache_enabled or is_cache_bypassed():
            return super().get(endpoint, params, custom_headers)

        ttl = self._cache.lookup_ttl(endpoint)
        if ttl == NO_CACHE:
            return super().get(endpoint, params, custom_headers)

        hit = self._cache.get(endpoint, params, self._token_hash, custom_headers)
        if hit is not MISS:
            return hit

        value = super().get(endpoint, params, custom_headers)
        self._cache.set(endpoint, params, self._token_hash, value, ttl, custom_headers)
        return value

    def close(self) -> None:
        try:
            self._cache.close()
        finally:
            super().close()
