from pathlib import Path

import pytest

from expense_tracker.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for var in ("EXPENSE_DB_PATH", "EXPENSE_USER_ID", "OPENROUTER_API_KEY", "OPENROUTER_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.owner_id == "local-demo"
    assert settings.openrouter_api_key is None
    assert settings.database_url.startswith("sqlite:///")


def test_blank_api_key_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
    assert Settings(_env_file=None).openrouter_api_key is None  # type: ignore[call-arg]


def test_secret_is_not_leaked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-super-secret")
    assert "sk-super-secret" not in repr(Settings(_env_file=None))  # type: ignore[call-arg]


def test_unrelated_env_file_keys_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=abc\nMONGODB_URI=x\nEXPENSE_USER_ID=alice\n")
    monkeypatch.delenv("EXPENSE_USER_ID", raising=False)
    assert Settings(_env_file=env).owner_id == "alice"  # type: ignore[call-arg]
