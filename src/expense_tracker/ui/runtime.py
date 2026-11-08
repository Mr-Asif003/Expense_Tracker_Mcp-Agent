"""Bridge between Streamlit's synchronous script model and the async AI host.

A dedicated daemon thread runs an asyncio event loop. That loop owns the MCP
session (via :class:`ExpenseToolbox`) and the LangGraph agent for as long as
the Streamlit server process lives, so reruns of the script never re-spawn the
MCP server.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import Any, TypeVar

from expense_tracker.config import Settings, get_settings
from expense_tracker.host.agent import build_agent
from expense_tracker.host.chat import ChatReply, ask
from expense_tracker.host.exceptions import ConfigurationError, HostError, McpConnectionError
from expense_tracker.host.toolbox import ExpenseToolbox

logger = logging.getLogger(__name__)

T = TypeVar("T")
STARTUP_TIMEOUT_S = 60
CHAT_TIMEOUT_S = 180


class HostRuntime:
    """Owns the background loop, MCP session and agent."""

    def __init__(self, settings: Settings | None = None, llm: Any = None) -> None:
        self._settings = settings or get_settings()
        self._llm = llm
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="host-runtime", daemon=True)
        self._ready = threading.Event()
        self._stop: asyncio.Event | None = None
        self._toolbox: ExpenseToolbox | None = None
        self._agent: Any = None
        self._server_future: Future[None] | None = None
        self.startup_error: Exception | None = None
        self.agent_error: str | None = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> HostRuntime:
        self._thread.start()
        self._server_future = asyncio.run_coroutine_threadsafe(self._serve(), self._loop)
        if not self._ready.wait(STARTUP_TIMEOUT_S):
            self.startup_error = McpConnectionError("Timed out starting the MCP server.")
        return self

    def stop(self) -> None:
        if self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._server_future is not None:
            self._server_future.result(timeout=10)
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _serve(self) -> None:
        # The toolbox must be entered and exited in this single task.
        self._stop = asyncio.Event()
        try:
            async with ExpenseToolbox(self._settings) as toolbox:
                self._toolbox = toolbox
                try:
                    self._agent = build_agent(toolbox, self._settings, self._llm)
                except ConfigurationError as exc:
                    self.agent_error = str(exc)
                except Exception as exc:
                    logger.exception("Could not build the agent")
                    self.agent_error = f"Could not build the agent: {type(exc).__name__}"
                self._ready.set()
                await self._stop.wait()
        except Exception as exc:
            logger.exception("Host runtime failed")
            self.startup_error = exc
        finally:
            self._ready.set()

    # --------------------------------------------------------------- status
    @property
    def connected(self) -> bool:
        return self._toolbox is not None and self.startup_error is None

    @property
    def agent_ready(self) -> bool:
        return self.connected and self._agent is not None

    @property
    def tool_names(self) -> list[str]:
        return self._toolbox.tool_names if self._toolbox else []

    @property
    def agent_tool_names(self) -> list[str]:
        return [t.name for t in self._toolbox.agent_tools] if self._toolbox else []

    # ------------------------------------------------------------- operations
    def _run(self, coro: Coroutine[Any, Any, T], timeout: float) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool directly. Raises :class:`ToolCallError` on tool errors."""
        if self._toolbox is None:
            raise McpConnectionError("MCP server is not connected.")
        return self._run(self._toolbox.call(name, arguments), timeout=30)

    def chat(self, thread_id: str, text: str) -> ChatReply:
        """Send a message to the agent. Raises :class:`HostError` if no agent is available."""
        if self._agent is None:
            raise HostError(self.agent_error or "The AI agent is not available.")
        return self._run(ask(self._agent, thread_id, text), timeout=CHAT_TIMEOUT_S)
