"""MCP interface: tools perform actions, resources expose data, prompts guide workflows."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from expense_tracker.config import get_settings
from expense_tracker.core import memory, repository
from expense_tracker.core.database import init_db
from expense_tracker.core.exceptions import ExpenseTrackerError
from expense_tracker.core.schemas import ExpenseCreate, ExpenseUpdate
from expense_tracker.logging_config import configure_logging
from datetime import datetime
from zoneinfo import ZoneInfo
logger = logging.getLogger(__name__)

SCHEMA_DESCRIPTION = (
    "Tables:\n"
    "expenses(id, owner_id, amount_paise, currency, category, description, spent_on, "
    "created_at, updated_at)\n"
    "memory_items(id, owner_id, memory_key, memory_value, category, created_at, updated_at)\n"
    "audit_events(id, owner_id, action, entity_type, entity_id, details, created_at)\n"
    "Amounts are stored as integer paise. All queries are scoped to the server-configured owner."
)


P = ParamSpec("P")
R = TypeVar("R")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _format_validation_error(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or 'input'}: {err['msg']}" for err in exc.errors()
    )


def tool_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Turn expected domain/validation errors into clean MCP ``ToolError`` responses.

    Unexpected exceptions are left alone so they are logged with a traceback.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            raise ToolError(_format_validation_error(exc)) from exc
        except ExpenseTrackerError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def create_server() -> FastMCP:
    """Build the MCP server. Tool handlers resolve the owner at call time."""
    mcp = FastMCP("Expense Tracker")

    def owner() -> str:
        return get_settings().owner_id

    # ----------------------------------------------------------------- tools
    @mcp.tool()
    @tool_errors
    def add_expense(
        amount: float, category: str, description: str, spent_on: str
    ) -> dict[str, Any]:
        """Create an expense. Amount is in INR; date must be YYYY-MM-DD."""
        payload = ExpenseCreate.model_validate(
            {
                "amount": amount,
                "category": category,
                "description": description,
                "spent_on": spent_on,
            }
        )
        return repository.create_expense(owner(), payload)

    @mcp.tool()
    @tool_errors
    def list_expenses(
        month: str | None = None, category: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List expenses, optionally filtered by YYYY-MM month and category (max 200)."""
        return repository.list_expenses(owner(), month, category, limit)

    @mcp.tool()
    @tool_errors
    def get_expense(expense_id: int) -> dict[str, Any]:
        """Get one expense by ID, scoped to the server-configured user."""
        return repository.get_expense(owner(), expense_id)

    @mcp.tool()
    @tool_errors
    def update_expense(
        expense_id: int,
        amount: float | None = None,
        category: str | None = None,
        description: str | None = None,
        spent_on: str | None = None,
    ) -> dict[str, Any]:
        """Update selected fields of an expense. Supply at least one field besides expense_id."""
        changes = ExpenseUpdate.model_validate(
            {
                "amount": amount,
                "category": category,
                "description": description,
                "spent_on": spent_on,
            }
        )
        return repository.update_expense(owner(), expense_id, changes)

    @mcp.tool()
    @tool_errors
    def delete_expense(expense_id: int, confirm: bool = False) -> dict[str, Any]:
        """Delete an expense only when confirm=true after explicit user confirmation."""
        return repository.delete_expense(owner(), expense_id, confirm)

    @mcp.tool()
    @tool_errors
    def monthly_summary(month: str) -> dict[str, Any]:
        """Summarize recorded expenses for a month formatted YYYY-MM."""
        return repository.expense_summary(owner(), month)

    @mcp.tool()
    @tool_errors
    def remember_preference(key: str, value: str, category: str = "preference") -> dict[str, str]:
        """Save or update a durable memory item; categories: preference, goal, context."""
        return memory.remember(owner(), key, value, category)

    @mcp.tool()
    @tool_errors
    def recall_memory(key: str | None = None) -> list[dict[str, str]]:
        """Recall all stored memory items or one exact key."""
        return memory.recall(owner(), key)

    @mcp.tool()
    @tool_errors
    def search_memory(query: str) -> list[dict[str, str]]:
        """Search saved memory by key or text."""
        return memory.find_memories(owner(), query)

    @mcp.tool()
    @tool_errors
    def get_today_date()->str:
        """Return today's date in YYYY-MM-DD format"""
        return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")


    # ------------------------------------------------------------- resources
    @mcp.resource("expense://summary/{month}")
    def summary_resource(month: str) -> str:
        """Read-only monthly expense summary resource; month is YYYY-MM."""
        return _json(repository.expense_summary(owner(), month))

    @mcp.resource("expense://recent")
    def recent_expenses_resource() -> str:
        """Read-only resource containing the 20 most recent recorded expenses."""
        return _json(repository.list_expenses(owner(), limit=20))

    @mcp.resource("memory://all")
    def memory_resource() -> str:
        """Read-only resource listing persistent memory for the configured local user."""
        return _json(memory.recall(owner()))

    @mcp.resource("expense://database/schema")
    def database_schema_resource() -> str:
        """Describe the application data model without exposing raw database contents."""
        return SCHEMA_DESCRIPTION

    # --------------------------------------------------------------- prompts
    @mcp.prompt()
    def monthly_spending_review(month: str) -> str:
        """Create a reusable prompt for reviewing a month's spending."""
        return (
            f"Review the user's recorded expenses for {month}. First retrieve the "
            f"expense://summary/{month} resource. Explain totals and category distribution, "
            "identify notable patterns only when supported by the data, and suggest practical "
            "budget questions. Do not invent transactions, assume income, or present the output "
            "as professional financial advice. Ask before making any changes."
        )

    @mcp.prompt()
    def spending_coach(goal: str = "understand spending") -> str:
        """Create a reusable prompt for a cautious personal spending review."""
        return (
            f"Act as a careful expense-tracking assistant. The user's goal is: {goal}. "
            "Use the expense summary and saved memory only when relevant. Separate facts from "
            "suggestions, mention missing data, do not shame the user, and never create, update, "
            "or delete a transaction without clear user authorization."
        )

    return mcp


def main() -> None:
    """Console entry point: serve over STDIO (stdout is reserved for the protocol)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    for noisy in ("docket", "fastmcp", "mcp.server.lowlevel.server"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    init_db()
    logger.info("Starting Expense Tracker MCP server (db=%s)", settings.db_path)
    create_server().run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
