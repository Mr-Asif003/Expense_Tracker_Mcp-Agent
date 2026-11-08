"""AI-host tests: a real MCP subprocess, a scripted LLM, no network."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from expense_tracker.config import get_settings
from expense_tracker.host.agent import build_agent
from expense_tracker.host.chat import ask
from expense_tracker.host.exceptions import ConfigurationError, McpConnectionError, ToolCallError
from expense_tracker.host.llm import get_llm
from expense_tracker.host.toolbox import ExpenseToolbox
from tests.fakes import ScriptedChatModel

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("db_path")]


async def test_toolbox_hides_destructive_tools_from_the_llm() -> None:
    async with ExpenseToolbox() as toolbox:
        assert "delete_expense" in toolbox.tool_names  # reachable by the UI...
        assert "delete_expense" not in {t.name for t in toolbox.agent_tools}  # ...not by the LLM


async def test_toolbox_direct_calls_and_errors() -> None:
    async with ExpenseToolbox() as toolbox:
        assert await toolbox.call("recall_memory") == []
        added = await toolbox.call(
            "add_expense",
            {"amount": 42, "category": "food", "description": "tea", "spent_on": "2026-10-01"},
        )
        assert added["amount"] == "42.00"
        listed = await toolbox.call("list_expenses", {"month": "2026-10"})
        assert [e["id"] for e in listed] == [added["id"]]
        with pytest.raises(ToolCallError, match="Expense not found"):
            await toolbox.call("get_expense", {"expense_id": 999})
        with pytest.raises(KeyError):
            await toolbox.call("no_such_tool")


async def test_toolbox_reports_missing_interpreter(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from expense_tracker.config import reset_settings_cache

    monkeypatch.setenv("EXPENSE_MCP_PYTHON", str(tmp_path / "missing-python"))
    reset_settings_cache()
    with pytest.raises(McpConnectionError, match="not found"):
        async with ExpenseToolbox():
            pass


async def test_subprocess_only_receives_whitelisted_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from expense_tracker.config import reset_settings_cache
    from expense_tracker.host.toolbox import build_mcp_client

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-should-not-leak")
    reset_settings_cache()
    client = build_mcp_client(get_settings())
    env = client.connections["expense_tracker"]["env"]
    assert "OPENROUTER_API_KEY" not in env
    assert set(env) >= {"EXPENSE_DB_PATH", "EXPENSE_USER_ID"}


async def test_agent_calls_mcp_tool_and_reports_it() -> None:
    llm = ScriptedChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add_expense",
                        "args": {
                            "amount": 250,
                            "category": "food",
                            "description": "Lunch",
                            "spent_on": "2026-10-27",
                        },
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="Added ₹250 for lunch."),
        ]
    )
    async with ExpenseToolbox() as toolbox:
        agent = build_agent(toolbox, llm=llm)
        reply = await ask(agent, "t1", "add 250 for lunch")
        assert reply.text == "Added ₹250 for lunch."
        assert [t.name for t in reply.tool_calls] == ["add_expense"]
        assert reply.tool_calls[0].arguments["amount"] == 250
        assert '"amount":"250.00"' in reply.tool_calls[0].result.replace(" ", "")
        # The write really went through the MCP server into the database.
        assert len(await toolbox.call("list_expenses", {"month": "2026-10"})) == 1


async def test_agent_keeps_conversation_state_per_thread() -> None:
    llm = ScriptedChatModel(script=[AIMessage(content="one"), AIMessage(content="two")])
    async with ExpenseToolbox() as toolbox:
        agent = build_agent(toolbox, llm=llm)
        first = await ask(agent, "thread-a", "hi")
        second = await ask(agent, "thread-a", "again")
        assert (first.text, second.text) == ("one", "two")
        assert second.tool_calls == []  # traces only include the current turn


def test_get_llm_requires_api_key() -> None:
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
        get_llm(get_settings())
