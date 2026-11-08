"""Centralised, typed application settings.

All configuration comes from environment variables (optionally loaded from a
``.env`` file). Nothing in this module performs I/O at import time; call
:func:`get_settings` to obtain the (cached) settings object.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by the MCP server, the AI host and the UI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # a shared .env may hold unrelated keys
        populate_by_name=True,
    )

    # --- Data layer / MCP server ------------------------------------------------
    db_path: Path = Field(
        default=Path("./data/expenses.db"),
        validation_alias=AliasChoices("EXPENSE_DB_PATH", "db_path"),
        description="SQLite database file.",
    )
    owner_id: str = Field(
        default="local-demo",
        validation_alias=AliasChoices("EXPENSE_USER_ID", "owner_id"),
        description=(
            "Server-side data scope for this single-user app. NOT authentication: "
            "derive the owner from a verified principal in a multi-user deployment."
        ),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("EXPENSE_LOG_LEVEL", "log_level"),
    )

    # --- AI host ----------------------------------------------------------------
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "openrouter_api_key"),
    )
    openrouter_model: str = Field(
        default="deepseek/deepseek-r1:free",
        validation_alias=AliasChoices("OPENROUTER_MODEL", "openrouter_model"),
    )
    llm_temperature: float = Field(
        default=0.2,
        ge=0,
        le=2,
        validation_alias=AliasChoices("EXPENSE_LLM_TEMPERATURE", "llm_temperature"),
    )
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    mcp_python: Path = Field(
        default=Path(sys.executable),
        validation_alias=AliasChoices("EXPENSE_MCP_PYTHON", "mcp_python"),
        description="Interpreter used to spawn the MCP server subprocess.",
    )
    default_thread_id: str = Field(
        default="local-expense-user",
        validation_alias=AliasChoices("EXPENSE_THREAD_ID", "default_thread_id"),
    )

    @field_validator("openrouter_api_key", mode="before")
    @classmethod
    def _blank_key_is_missing(cls, value: object) -> object:
        """Treat ``OPENROUTER_API_KEY=`` (empty) in a .env file as not set."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.expanduser().resolve()}"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached settings (used by tests)."""
    get_settings.cache_clear()
