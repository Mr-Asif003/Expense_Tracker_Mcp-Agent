"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from expense_tracker.config import reset_settings_cache
from expense_tracker.core import database

OWNER = "test-owner"


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every component at an isolated temporary database."""
    path = tmp_path / "expenses.db"
    monkeypatch.setenv("EXPENSE_DB_PATH", str(path))
    monkeypatch.setenv("EXPENSE_USER_ID", OWNER)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.chdir(tmp_path)  # keeps any stray .env lookups away from the repo
    reset_settings_cache()
    return path


@pytest.fixture
def db(db_path: Path) -> Iterator[Path]:
    """An initialised, empty database for in-process tests."""
    database.configure_database()
    database.init_db()
    yield db_path
    database.get_engine().dispose()
    reset_settings_cache()


@pytest.fixture
def owner() -> str:
    return OWNER
