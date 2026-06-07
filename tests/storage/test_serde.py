"""Regression tests for the project's checkpoint serializer."""

from __future__ import annotations

import logging
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from integrations.github.models import RepositoryRecord
from storage.serde import make_sync_sqlite_saver

_LANGGRAPH_SERDE_LOGGER = "langgraph.checkpoint.serde.jsonplus"


def _roundtrip(saver, repo: RepositoryRecord) -> RepositoryRecord:
    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 3,
        "id": "1",
        "ts": "2024-01-01T00:00:00Z",
        "channel_values": {"tracked_repositories": [repo]},
        "channel_versions": {"tracked_repositories": 1},
        "versions_seen": {},
    }
    saver.put(
        config,
        checkpoint,
        {"source": "input", "step": 0, "parents": {}},
        {"tracked_repositories": "1"},
    )
    got = saver.get(config)
    assert got is not None
    return got["channel_values"]["tracked_repositories"][0]


def _unregistered_warnings(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == _LANGGRAPH_SERDE_LOGGER
        and "unregistered type" in record.getMessage()
    ]


def test_configured_serde_roundtrips_repository_record_without_warning(
    tmp_path, caplog
):
    """The configured saver should deserialize RepositoryRecord silently."""
    repo = RepositoryRecord(name="o/r", stars=1, url="http://example/r")

    with caplog.at_level(logging.WARNING, logger=_LANGGRAPH_SERDE_LOGGER):
        with sqlite3.connect(tmp_path / "b.db") as conn:
            saver = make_sync_sqlite_saver(conn)
            saver.setup()
            recovered = _roundtrip(saver, repo)

    assert isinstance(recovered, RepositoryRecord)
    assert recovered.name == "o/r"
    assert _unregistered_warnings(caplog) == []


def test_default_serde_warns_on_repository_record(tmp_path, caplog):
    """Sanity-check the framework: the default saver still emits the warning.

    If this test ever starts failing it means LangGraph either changed the
    warning text or its default policy — at which point the suppression test
    above needs revisiting too.
    """
    # LangGraph dedups the warning per (module, name) at process scope; clear
    # the cache so a prior test run in the same process can't hide it here.
    from langgraph.checkpoint.serde import jsonplus as _jp

    _jp._warned_unregistered_types.discard(
        (RepositoryRecord.__module__, RepositoryRecord.__name__)
    )

    repo = RepositoryRecord(name="o/r", stars=1, url="http://example/r")

    with caplog.at_level(logging.WARNING, logger=_LANGGRAPH_SERDE_LOGGER):
        with sqlite3.connect(tmp_path / "a.db") as conn:
            saver = SqliteSaver(conn)
            saver.setup()
            _roundtrip(saver, repo)

    warnings_found = _unregistered_warnings(caplog)
    assert warnings_found, "expected LangGraph to warn about RepositoryRecord"
    assert "RepositoryRecord" in warnings_found[0]
