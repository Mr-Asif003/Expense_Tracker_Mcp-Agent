"""LLM factory (OpenRouter)."""

from __future__ import annotations

from typing import Any

from expense_tracker.config import Settings, get_settings
from expense_tracker.host.exceptions import ConfigurationError


def get_llm(settings: Settings | None = None) -> Any:
    """Create the chat model from settings.

    Raises:
        ConfigurationError: if ``OPENROUTER_API_KEY`` is not set.
    """
    settings = settings or get_settings()
    if settings.openrouter_api_key is None:
        raise ConfigurationError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    from langchain_openrouter import ChatOpenRouter  # imported lazily: heavy import

    return ChatOpenRouter(  # type: ignore[call-arg]  # field is aliased: model_name <-> model
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
    )
