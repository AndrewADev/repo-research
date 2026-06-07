"""Tests for CachedGitHubClient and the underlying GitHubCache.

HTTP is stubbed by patching ``GitHubClient._make_request`` — we never touch
the network. Cache state lives under ``tmp_path``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from integrations.github.cache import (
    DEFAULT_POLICIES,
    NO_CACHE,
    TTL_ACTIVITY,
    TTL_IMMUTABLE,
    TTL_ISSUES_PULLS,
    TTL_REPO_METADATA,
    TTL_STARRED,
    GitHubCache,
    no_cache,
)
from integrations.github.cached_client import CachedGitHubClient


def _stub_response(payload: Any) -> MagicMock:
    """Build a fake ``requests.Response`` whose ``.json()`` returns *payload*."""
    response = MagicMock()
    response.json.return_value = payload
    return response


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def cache(cache_dir: Path) -> GitHubCache:
    c = GitHubCache(path=cache_dir, size_limit=8 * 1024 * 1024)
    yield c
    c.close()


@pytest.fixture
def client(cache: GitHubCache, monkeypatch: pytest.MonkeyPatch) -> CachedGitHubClient:
    monkeypatch.delenv("GITHUB_AGENT_CACHE_DISABLE", raising=False)
    c = CachedGitHubClient(token="test-token-123", cache=cache)
    yield c
    # Don't double-close the cache (fixture owns it); just close the session.
    c.session.close()


class TestPolicyLookup:
    """Endpoint → TTL routing."""

    @pytest.mark.parametrize(
        "endpoint, expected_ttl",
        [
            ("/rate_limit", NO_CACHE),
            ("/repos/octo/cat/commits/abc1234", TTL_IMMUTABLE),
            (
                "/repos/octo/cat/commits/abcdef0123456789abcdef0123456789abcdef01",
                TTL_IMMUTABLE,
            ),
            ("/repos/octo/cat/git/blobs/deadbeef", TTL_IMMUTABLE),
            ("/repos/octo/cat/git/trees/cafebabe", TTL_IMMUTABLE),
            ("/repos/octo/cat/git/trees/main", TTL_ACTIVITY),
            ("/repos/octo/cat/git/trees/release-v2", TTL_ACTIVITY),
            ("/repos/octo/cat/commits", TTL_ACTIVITY),
            ("/search/repositories", TTL_ACTIVITY),
            ("/repos/octo/cat/issues", TTL_ISSUES_PULLS),
            ("/repos/octo/cat/pulls", TTL_ISSUES_PULLS),
            ("/repos/octo/cat/labels", TTL_REPO_METADATA),
            ("/repos/octo/cat", TTL_REPO_METADATA),
            ("/users/octo/starred", TTL_STARRED),
            ("/user/starred", TTL_STARRED),
            ("/users/octo", TTL_REPO_METADATA),
            ("/user", TTL_REPO_METADATA),
            # Unmatched defaults to no-cache.
            ("/some/unknown/endpoint", NO_CACHE),
        ],
    )
    def test_lookup_ttl(
        self, cache: GitHubCache, endpoint: str, expected_ttl: Any
    ) -> None:
        assert cache.lookup_ttl(endpoint) == expected_ttl


class TestCacheHitMiss:
    def test_cache_hit_avoids_second_http_call(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = MagicMock(return_value=_stub_response({"id": 1, "full_name": "o/r"}))
        monkeypatch.setattr(client, "_make_request", stub)

        first = client.get("/repos/o/r")
        second = client.get("/repos/o/r")

        assert first == second == {"id": 1, "full_name": "o/r"}
        assert stub.call_count == 1

    def test_different_params_are_different_entries(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        responses = [_stub_response([{"sha": "a"}]), _stub_response([{"sha": "b"}])]
        stub = MagicMock(side_effect=responses)
        monkeypatch.setattr(client, "_make_request", stub)

        a = client.get("/repos/o/r/commits", {"path": "x"})
        b = client.get("/repos/o/r/commits", {"path": "y"})

        assert a != b
        assert stub.call_count == 2

    def test_different_custom_headers_are_different_entries(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom Accept headers negotiate response shape — e.g. a blob fetched
        as raw bytes vs. as JSON. They must not collide in the cache.
        """
        json_resp = _stub_response({"content": "base64==", "encoding": "base64"})
        raw_resp = _stub_response(b"raw bytes from blob")
        stub = MagicMock(side_effect=[json_resp, raw_resp])
        monkeypatch.setattr(client, "_make_request", stub)

        endpoint = "/repos/o/r/git/blobs/deadbeef0"
        as_json = client.get(endpoint)  # default Accept (JSON)
        as_raw = client.get(
            endpoint, custom_headers={"Accept": "application/vnd.github.raw"}
        )

        assert as_json == {"content": "base64==", "encoding": "base64"}
        assert as_raw == b"raw bytes from blob"
        assert stub.call_count == 2

    def test_same_custom_headers_share_entry(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated calls with the same custom_headers should hit the cache."""
        stub = MagicMock(return_value=_stub_response({"id": 1, "topics": ["x"]}))
        monkeypatch.setattr(client, "_make_request", stub)

        headers = {"Accept": "application/vnd.github.mercy-preview+json"}
        # Pass a fresh dict on the second call to confirm the key depends on
        # *contents*, not on object identity.
        a = client.get("/repos/o/r", custom_headers=headers)
        b = client.get("/repos/o/r", custom_headers=dict(headers))
        assert a == b
        assert stub.call_count == 1

    def test_rate_limit_never_cached(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = MagicMock(return_value=_stub_response({"resources": {}}))
        monkeypatch.setattr(client, "_make_request", stub)

        client.get("/rate_limit")
        client.get("/rate_limit")

        assert stub.call_count == 2


class TestNoCacheContext:
    def test_no_cache_context_bypasses_lookup_and_store(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        responses = [_stub_response({"v": 1}), _stub_response({"v": 2})]
        stub = MagicMock(side_effect=responses)
        monkeypatch.setattr(client, "_make_request", stub)

        with no_cache():
            first = client.get("/repos/o/r")
            second = client.get("/repos/o/r")
        assert first == {"v": 1}
        assert second == {"v": 2}
        assert stub.call_count == 2

        # And the cache stays empty, so a normal call still misses.
        stub.side_effect = [_stub_response({"v": 3})]
        stub.reset_mock()
        third = client.get("/repos/o/r")
        assert third == {"v": 3}
        assert stub.call_count == 1

    def test_no_cache_context_propagates_through_pagination(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two-page response: full page, then partial page (terminator).
        page1 = _stub_response([{"sha": f"c{i}"} for i in range(100)])
        page2 = _stub_response([{"sha": "tail"}])
        stub = MagicMock(side_effect=[page1, page2])
        monkeypatch.setattr(client, "_make_request", stub)

        with no_cache():
            items = client.get_paginated("/repos/o/r/commits")
        assert len(items) == 101
        assert stub.call_count == 2

        # Cache wasn't written — repeating outside the context triggers
        # fresh fetches.
        stub.side_effect = [
            _stub_response([{"sha": f"d{i}"} for i in range(100)]),
            _stub_response([{"sha": "tail2"}]),
        ]
        stub.reset_mock()
        client.get_paginated("/repos/o/r/commits")
        assert stub.call_count == 2

    def test_no_cache_context_is_scoped(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After leaving the no_cache() block, caching resumes normally."""
        stub = MagicMock(
            side_effect=[
                _stub_response({"v": 1}),  # bypassed call inside no_cache()
                _stub_response({"v": 2}),  # cached call outside
            ]
        )
        monkeypatch.setattr(client, "_make_request", stub)

        with no_cache():
            client.get("/repos/o/r")
        client.get("/repos/o/r")  # cache MISS, then stored
        client.get("/repos/o/r")  # cache HIT
        assert stub.call_count == 2


class TestEnabledFlag:
    def test_enabled_false_disables_caching(
        self, cache: GitHubCache, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GITHUB_AGENT_CACHE_DISABLE", raising=False)
        c = CachedGitHubClient(token="t", cache=cache, enabled=False)
        stub = MagicMock(
            side_effect=[_stub_response({"v": 1}), _stub_response({"v": 2})]
        )
        monkeypatch.setattr(c, "_make_request", stub)

        a = c.get("/repos/o/r")
        b = c.get("/repos/o/r")
        assert a != b
        assert stub.call_count == 2

    @pytest.mark.parametrize("env_value", ["1", "true", "TRUE"])
    def test_env_var_disables_caching(
        self,
        cache: GitHubCache,
        monkeypatch: pytest.MonkeyPatch,
        env_value: str,
    ) -> None:
        monkeypatch.setenv("GITHUB_AGENT_CACHE_DISABLE", env_value)
        c = CachedGitHubClient(token="t", cache=cache)
        stub = MagicMock(
            side_effect=[_stub_response({"v": 1}), _stub_response({"v": 2})]
        )
        monkeypatch.setattr(c, "_make_request", stub)

        c.get("/repos/o/r")
        c.get("/repos/o/r")
        assert stub.call_count == 2


class TestTTL:
    def test_ttl_expiry(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a short-TTL response is re-fetched after expiry.

        diskcache evaluates expiry against real wall time, so this test sets
        the TTL via a hand-crafted GitHubCache with a 1-second policy and
        sleeps briefly.
        """
        # Replace the policy table for /repos/o/r with a 1-second TTL.
        import re

        from integrations.github.cache import CachePolicy

        short = CachePolicy(pattern=re.compile(r"^/repos/o/r$"), ttl=1)
        client._cache._policies = [short, *DEFAULT_POLICIES]

        stub = MagicMock(
            side_effect=[_stub_response({"v": 1}), _stub_response({"v": 2})]
        )
        monkeypatch.setattr(client, "_make_request", stub)

        first = client.get("/repos/o/r")
        assert first == {"v": 1}
        assert stub.call_count == 1

        time.sleep(1.2)

        second = client.get("/repos/o/r")
        assert second == {"v": 2}
        assert stub.call_count == 2


class TestImmutableAndLRU:
    def test_blob_is_immutable_cached(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = MagicMock(return_value=_stub_response({"content": "blob-bytes"}))
        monkeypatch.setattr(client, "_make_request", stub)

        client.get("/repos/o/r/git/blobs/deadbeef00")
        client.get("/repos/o/r/git/blobs/deadbeef00")
        client.get("/repos/o/r/git/blobs/deadbeef00")
        assert stub.call_count == 1

    def test_tree_sha_vs_ref(
        self, client: CachedGitHubClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert client._cache.lookup_ttl("/repos/o/r/git/trees/abc1234") == TTL_IMMUTABLE
        assert client._cache.lookup_ttl("/repos/o/r/git/trees/main") == TTL_ACTIVITY

    def test_size_limit_triggers_eviction(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A tiny cache filled with many large entries evicts some — smoke test
        that ``size_limit`` is actually being honored by diskcache. Which
        entries survive is a diskcache implementation detail (governed by the
        ``least-recently-used`` policy) and not asserted here.
        """
        tiny = GitHubCache(path=tmp_path / "tiny", size_limit=64 * 1024)
        try:
            c = CachedGitHubClient(token="t", cache=tiny)
            try:
                payload = "x" * 20_000  # ~20KB each — only a few fit in 64KB.

                def fake_request(*args: Any, **kwargs: Any) -> MagicMock:
                    sha = args[1].rsplit("/", 1)[-1]
                    return _stub_response({"sha": sha, "blob": payload})

                monkeypatch.setattr(c, "_make_request", fake_request)

                inserted = 20
                for i in range(inserted):
                    c.get(f"/repos/o/r/commits/{i:040x}")
                tiny._cache.cull()

                # Diskcache should have evicted at least some entries — strictly
                # fewer entries than we inserted should remain.
                assert len(tiny._cache) < inserted
            finally:
                c.session.close()
        finally:
            tiny.close()


class TestTokenIsolation:
    def test_different_tokens_dont_share_entries(
        self, cache: GitHubCache, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        a = CachedGitHubClient(token="alice", cache=cache)
        b = CachedGitHubClient(token="bob", cache=cache)
        try:
            stub_a = MagicMock(return_value=_stub_response({"who": "alice"}))
            stub_b = MagicMock(return_value=_stub_response({"who": "bob"}))
            monkeypatch.setattr(a, "_make_request", stub_a)
            monkeypatch.setattr(b, "_make_request", stub_b)

            assert a.get("/user") == {"who": "alice"}
            # Bob should miss and call out — not see alice's entry.
            assert b.get("/user") == {"who": "bob"}
            assert stub_a.call_count == 1
            assert stub_b.call_count == 1
        finally:
            a.session.close()
            b.session.close()
