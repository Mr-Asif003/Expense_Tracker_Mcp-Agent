"""A persistent MCP STDIO session exposed as LangChain tools.

The original implementation spawned a new server subprocess for *every* tool
call. Here one subprocess and one MCP session are kept open for the lifetime
of the toolbox, which is much faster and keeps state consistent.

The toolbox must be entered and exited from the same asyncio task
(``async with toolbox:``); calls to :meth:`call` may come from any task on the
same event loop.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from expense_tracker.config import Settings, get_settings
from expense_tracker.host.exceptions import McpConnectionError, ToolCallError
from expense_tracker.host.results import content_to_text, parse_tool_result

logger = logging.getLogger(__name__)

SERVER_NAME = "expense_tracker"

# Tools that the LLM must never see. Destructive operations stay out of reach
# of the model; a human-facing UI must implement its own confirmation flow.
DEFAULT_BLOCKED_TOOLS: frozenset[str] = frozenset({"delete_expense"})


def build_mcp_client(settings: Settings) -> MultiServerMCPClient:
    """Configure the MCP server subprocess (STDIO transport).

    Only the variables the server needs are forwarded, so unrelated secrets
    (LLM API keys, tracing keys...) never reach the subprocess.
    """
    env = {
        "EXPENSE_DB_PATH": str(settings.db_path.expanduser().resolve()),
        "EXPENSE_USER_ID": settings.owner_id,
        "EXPENSE_LOG_LEVEL": settings.log_level,
        "PYTHONUNBUFFERED": "1",
    }
    return MultiServerMCPClient(
        {
            SERVER_NAME: {
                "transport": "stdio",
                "command": str(settings.mcp_python),
                "args": ["-m", "expense_tracker.mcp_server"],
                "env": env,
            }
        }
    )


class ExpenseToolbox:
    """Async context manager owning the MCP session and its tools."""

    def __init__(
        self,
        settings: Settings | None = None,
        blocked_tools: frozenset[str] = DEFAULT_BLOCKED_TOOLS,
    ) -> None:
        self._settings = settings or get_settings()
        self._blocked = blocked_tools
        self._stack = AsyncExitStack()
        self._all_tools: dict[str, BaseTool] = {}
        self._session: Any = None

    async def __aenter__(self) -> ExpenseToolbox:
        python = self._settings.mcp_python
        if not python.is_file():
            raise McpConnectionError(f"MCP Python executable not found: {python}")
        client = build_mcp_client(self._settings)
        try:
            self._session = await self._stack.enter_async_context(client.session(SERVER_NAME))
            tools = await load_mcp_tools(self._session)
        except Exception as exc:
            await self._stack.aclose()
            raise McpConnectionError(
                "Could not connect to the Expense Tracker MCP server. "
                "Check EXPENSE_MCP_PYTHON and that the package is installed."
            ) from exc
        self._all_tools = {tool.name: tool for tool in tools}
        if not self._all_tools:
            await self._stack.aclose()
            raise McpConnectionError("The MCP server exposed no tools.")
        logger.info("Connected to MCP server; tools: %s", ", ".join(self._all_tools))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._stack.aclose()

    @property
    def tool_names(self) -> list[str]:
        return list(self._all_tools)

    @property
    def agent_tools(self) -> list[BaseTool]:
        """Tools the LLM is allowed to use."""
        return [t for t in self._all_tools.values() if t.name not in self._blocked]

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool directly (for UI/non-LLM use) and return the parsed JSON result.

        This goes through the raw MCP session, so server-side errors are
        reported reliably via ``isError``.

        Raises:
            KeyError: unknown tool.
            ToolCallError: the tool reported an error.
        """
        if name not in self._all_tools:
            raise KeyError(name)
        result = await self._session.call_tool(name, arguments or {})
        text = content_to_text(
            [{"type": "text", "text": b.text} for b in result.content if b.type == "text"]
        )
        if result.isError:
            raise ToolCallError(text or f"Tool {name!r} failed")
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            # FastMCP wraps non-object return values (e.g. lists) as {"result": ...}.
            return structured["result"] if set(structured) == {"result"} else structured
        return parse_tool_result(text)
