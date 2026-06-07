"""Tests for the legacy ~/.github-agent → ~/.repo-research auto-migration."""

from pathlib import Path

import pytest

from repo_research import storage_paths


@pytest.fixture(autouse=True)
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect Path.home() to tmp_path and reset the once-per-process guard."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(storage_paths, "_migrated", False)
    return tmp_path


def test_migrates_when_only_old_exists(fake_home: Path) -> None:
    old = fake_home / storage_paths.OLD_DIR_NAME
    old.mkdir()
    (old / "conversations.db").write_text("legacy")

    root = storage_paths.storage_root()

    assert root == fake_home / storage_paths.NEW_DIR_NAME
    assert root.exists()
    assert (root / "conversations.db").read_text() == "legacy"
    assert not old.exists()


def test_no_migration_when_new_already_exists(fake_home: Path) -> None:
    old = fake_home / storage_paths.OLD_DIR_NAME
    new = fake_home / storage_paths.NEW_DIR_NAME
    old.mkdir()
    (old / "conversations.db").write_text("legacy")
    new.mkdir()
    (new / "conversations.db").write_text("current")

    root = storage_paths.storage_root()

    assert root == new
    assert (new / "conversations.db").read_text() == "current"
    assert old.exists()


def test_creates_new_when_neither_exists(fake_home: Path) -> None:
    root = storage_paths.storage_root()

    assert root == fake_home / storage_paths.NEW_DIR_NAME
    assert root.exists()


def test_migration_runs_only_once(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = fake_home / storage_paths.OLD_DIR_NAME
    old.mkdir()

    storage_paths.storage_root()
    # Re-create the legacy dir; a second call should NOT migrate it again.
    old.mkdir()

    root = storage_paths.storage_root()
    assert old.exists()
    assert root == fake_home / storage_paths.NEW_DIR_NAME
