"""Shared user-data storage root for repo-research.

Owns the on-disk migration from the legacy ``~/.github-agent/`` directory.
Both the conversation DB and the GitHub disk cache live under the same root,
so this module is the single source of truth for that path.
"""

import logging
from pathlib import Path

OLD_DIR_NAME = ".github-agent"
NEW_DIR_NAME = ".repo-research"

logger = logging.getLogger(__name__)

_migrated = False


def _new_dir() -> Path:
    return Path.home() / NEW_DIR_NAME


def _old_dir() -> Path:
    return Path.home() / OLD_DIR_NAME


def storage_root() -> Path:
    """Return the storage root, migrating from the legacy location on first call."""
    global _migrated
    if not _migrated:
        _maybe_migrate()
        _migrated = True
    new = _new_dir()
    new.mkdir(exist_ok=True)
    return new


def _maybe_migrate() -> None:
    new = _new_dir()
    old = _old_dir()
    if new.exists() or not old.exists():
        return
    old.rename(new)
    logger.info("Migrated storage directory %s -> %s", old, new)
