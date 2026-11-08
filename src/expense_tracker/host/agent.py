"""Agent construction."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from expense_tracker.config import Settings, get_settings
from expense_tracker.host.llm import get_llm
from expense_tracker.host.prompts import SYSTEM_PROMPT
from expense_tracker.host.toolbox import ExpenseToolbox


def build_agent(toolbox: ExpenseToolbox, settings: Settings | None = None, llm: Any = None) -> Any:
    """Create the expense agent with MCP tools and in-memory conversation state.

    ``llm`` can be injected (tests, alternative providers); otherwise it is
    created from settings.
    """
    settings = settings or get_settings()
    return create_agent(
        model=llm if llm is not None else get_llm(settings),
        tools=toolbox.agent_tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )
