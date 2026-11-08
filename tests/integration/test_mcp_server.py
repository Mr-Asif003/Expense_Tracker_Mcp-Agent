"""MCP server tests using FastMCP's in-memory client (no subprocess)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from expense_tracker.mcp_server.server import SCHEMA_DESCRIPTION, create_server

pytestmark = pytest.mark.usefixtures("db")


@pytest.fixture
async def client():
    async with Client(create_server()) as c:
        yield c


async def test_exposes_expected_primitives(client: Client) -> None:
    tools = {t.name for t in await client.list_tools()}
    assert tools == {
        "add_expense", "list_expenses", "get_expense", "update_expense", "delete_expense",
        "monthly_summary", "remember_preference", "recall_memory", "search_memory",
    }  # fmt: skip
    prompts = {p.name for p in await client.list_prompts()}
    assert prompts == {"monthly_spending_review", "spending_coach"}


async def test_add_then_summarise(client: Client) -> None:
    added = await client.call_tool(
        "add_expense",
        {"amount": 125.5, "category": "Food", "description": "Lunch", "spent_on": "2026-10-27"},
    )
    assert added.data["category"] == "food"
    summary = await client.call_tool("monthly_summary", {"month": "2026-10"})
    assert summary.data["total"] == "₹125.50"


async def test_validation_errors_become_clean_tool_errors(client: Client) -> None:
    with pytest.raises(ToolError, match="category must be one of"):
        await client.call_tool(
            "add_expense",
            {"amount": 5, "category": "nope", "description": "x", "spent_on": "2026-10-27"},
        )
    with pytest.raises(ToolError, match="Expense not found"):
        await client.call_tool("get_expense", {"expense_id": 12345})
    with pytest.raises(ToolError, match="at least one field"):
        await client.call_tool("update_expense", {"expense_id": 1})


async def test_delete_needs_confirmation(client: Client) -> None:
    added = await client.call_tool(
        "add_expense",
        {"amount": 5, "category": "food", "description": "x", "spent_on": "2026-10-27"},
    )
    expense_id = added.data["id"]
    with pytest.raises(ToolError, match="confirm"):
        await client.call_tool("delete_expense", {"expense_id": expense_id})
    result = await client.call_tool("delete_expense", {"expense_id": expense_id, "confirm": True})
    assert result.data["deleted"] is True


async def test_memory_roundtrip(client: Client) -> None:
    await client.call_tool(
        "remember_preference", {"key": "budget", "value": "₹15000", "category": "goal"}
    )
    found = await client.call_tool("search_memory", {"query": "budget"})
    assert found.structured_content["result"][0]["value"] == "₹15000"


async def test_resources(client: Client) -> None:
    await client.call_tool(
        "add_expense",
        {"amount": 10, "category": "food", "description": "x", "spent_on": "2026-10-27"},
    )
    summary = await client.read_resource("expense://summary/2026-10")
    assert json.loads(summary[0].text)["transaction_count"] == 1
    recent = await client.read_resource("expense://recent")
    assert len(json.loads(recent[0].text)) == 1
    schema = await client.read_resource("expense://database/schema")
    assert schema[0].text == SCHEMA_DESCRIPTION


def test_schema_resource_uses_real_newlines() -> None:
    """Regression: v0.1 emitted a literal backslash-n sequence."""
    assert "\\n" not in SCHEMA_DESCRIPTION
    assert SCHEMA_DESCRIPTION.count("\n") >= 3


async def test_prompts_render(client: Client) -> None:
    result = await client.get_prompt("monthly_spending_review", {"month": "2026-10"})
    assert "expense://summary/2026-10" in str(result.messages[0].content)
