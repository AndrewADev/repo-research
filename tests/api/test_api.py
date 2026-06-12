"""Tests for the FastAPI HTTP layer (REST endpoints + AG-UI SSE stream)."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from ag_ui.core import (
    BaseEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from fastapi.testclient import TestClient

from api.app import create_app


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient whose stores point at a throwaway SQLite DB."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("storage.conversations.default_db_path", lambda: db_path)
    monkeypatch.setattr("storage.favorites.default_db_path", lambda: db_path)
    with TestClient(create_app()) as test_client:
        yield test_client


def test_config_endpoint(client: TestClient) -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "provider" in body
    assert "model_name" in body
    assert "Python" in body["languages"]


def test_conversations_empty(client: TestClient) -> None:
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_missing_conversation_returns_404(client: TestClient) -> None:
    resp = client.get("/api/conversations/does-not-exist")
    assert resp.status_code == 404


def test_favorites_crud(client: TestClient) -> None:
    # Initially empty.
    assert client.get("/api/favorites").json()["saved_repos"] == []

    # Add one.
    repo = {
        "full_name": "owner/repo",
        "url": "https://github.com/owner/repo",
        "stars": 42,
        "language": "Python",
        "topics": ["ai", "ml"],
        "description": "A test repo",
    }
    resp = client.post("/api/favorites", json=repo)
    assert resp.status_code == 200
    saved = resp.json()["saved_repos"]
    assert len(saved) == 1
    assert saved[0]["full_name"] == "owner/repo"

    # Adding the same one again is idempotent.
    resp = client.post("/api/favorites", json=repo)
    assert len(resp.json()["saved_repos"]) == 1

    # Export as CSV.
    resp = client.get("/api/favorites/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "owner/repo" in resp.text

    # Remove it (full name contains a slash -> needs the :path converter).
    resp = client.delete("/api/favorites/owner/repo")
    assert resp.status_code == 200
    assert resp.json()["saved_repos"] == []

    # Removing again is a 404.
    assert client.delete("/api/favorites/owner/repo").status_code == 404


def _fake_event_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[BaseEvent]:
    async def _gen() -> AsyncIterator[BaseEvent]:
        yield RunStartedEvent(thread_id="t1", run_id="r1")
        yield TextMessageStartEvent(message_id="m1")
        yield TextMessageContentEvent(message_id="m1", delta="hello world")
        yield TextMessageEndEvent(message_id="m1")
        # raw_event carries a non-serializable Exception; the endpoint must
        # strip it before encoding to the wire.
        yield RunErrorEvent(message="boom", code="X", raw_event=ValueError("boom"))
        yield RunFinishedEvent(thread_id="t1", run_id="r1")

    return _gen()


def test_agent_endpoint_streams_sse(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _DummyGraph:
        checkpointer: Any = None

    monkeypatch.setattr(
        "api.agent_endpoint.create_configured_agent", lambda *a, **k: _DummyGraph()
    )
    monkeypatch.setattr(
        "api.agent_endpoint.close_agent_resources", lambda *a, **k: None
    )
    monkeypatch.setattr("api.agent_endpoint.emit_agui_events", _fake_event_stream)

    payload = {
        "threadId": "t1",
        "runId": "r1",
        "state": {},
        "messages": [{"id": "1", "role": "user", "content": "hi"}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    resp = client.post("/agent", json=payload)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    # SSE framing + content survived, and the error event encoded without its
    # un-serializable raw_event payload.
    assert "data: " in body
    assert "hello world" in body
    assert "RUN_STARTED" in body
    assert "RUN_ERROR" in body
    assert "RUN_FINISHED" in body
