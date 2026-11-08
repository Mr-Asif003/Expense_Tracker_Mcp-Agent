"""Interactive terminal chat (``expense-tracker-agent``)."""

from __future__ import annotations

import asyncio
import logging

from expense_tracker.config import get_settings
from expense_tracker.host.agent import build_agent
from expense_tracker.host.chat import ask
from expense_tracker.host.exceptions import HostError
from expense_tracker.host.llm import get_llm
from expense_tracker.host.toolbox import ExpenseToolbox
from expense_tracker.logging_config import configure_logging

logger = logging.getLogger(__name__)

BANNER = """
========================================
       Expense Tracker AI
========================================
Ask questions about your expenses or saved memory.
Commands: exit, quit
"""


async def run_chat() -> None:
    settings = get_settings()
    llm = get_llm(settings)  # fail fast on a missing API key, before starting the MCP server
    async with ExpenseToolbox(settings) as toolbox:
        agent = build_agent(toolbox, settings, llm)
        print(BANNER)
        print("Tools:", ", ".join(t.name for t in toolbox.agent_tools), "\n")
        while True:
            try:
                user_input = (await asyncio.to_thread(input, "You: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                return
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("Goodbye!")
                return
            try:
                reply = await ask(agent, settings.default_thread_id, user_input)
                print(f"\nAssistant: {reply.text}\n")
            except Exception as exc:
                # Log details to stderr; keep the terminal output free of secrets/tracebacks.
                logger.exception("Chat request failed")
                print(f"\nAssistant: The request failed ({type(exc).__name__}). See the log.\n")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        asyncio.run(run_chat())
    except HostError as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
