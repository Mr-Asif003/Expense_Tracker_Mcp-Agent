"""Streamlit UI tests with Streamlit's headless AppTest harness."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from expense_tracker.config import get_settings
from expense_tracker.ui import app as ui_app

APP = str(Path(ui_app.__file__))

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("db_path")]


@pytest.fixture
def at() -> Iterator[AppTest]:
    test = AppTest.from_file(APP, default_timeout=60).run()
    yield test
    ui_app.get_runtime.clear()  # stops reuse of the MCP subprocess between tests


def _go(test: AppTest, view: str) -> AppTest:
    test.sidebar.radio[0].set_value(view).run()
    assert not test.exception, [e.value for e in test.exception]
    return test


def test_starts_without_llm_key_and_still_serves_dashboard(at: AppTest) -> None:
    assert not at.exception
    assert any("connected" in s.value for s in at.sidebar.success)
    assert any("Agent unavailable" in w.value for w in at.sidebar.warning)
    assert any("OPENROUTER_API_KEY" in i.value for i in at.info)
    assert at.chat_input[0].disabled  # can't chat without an agent

    _go(at, "📊 Dashboard")
    assert any("No expenses" in i.value for i in at.info)


def test_add_expense_updates_dashboard(at: AppTest) -> None:
    _go(at, "📊 Dashboard")
    at.text_input[0].set_value("Chai")
    next(b for b in at.button if b.label == "Add expense").click()
    at.run()
    assert not at.exception
    assert any("Expense added" in s.value for s in at.success)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Transactions"] == "1"
    assert metrics["Total spent"] == "₹100.00"


def test_form_errors_are_shown_not_raised(at: AppTest) -> None:
    _go(at, "📊 Dashboard")
    next(b for b in at.button if b.label == "Add expense").click()  # blank description
    at.run()
    assert not at.exception
    assert any("description" in e.value for e in at.error)


def test_memory_roundtrip(at: AppTest) -> None:
    _go(at, "🧠 Memory")
    assert any("Nothing saved" in i.value for i in at.info)
    at.text_input[0].set_value("monthly_budget")
    at.text_area[0].set_value("₹15000")
    next(b for b in at.button if b.label == "Save").click()
    at.run()
    assert not at.exception
    assert len(at.dataframe) == 1


def _script() -> None:
    from expense_tracker.ui import app

    app.main()


def test_chat_end_to_end_with_scripted_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real UI + real runtime + real MCP subprocess; only the LLM is scripted."""
    from langchain_core.messages import AIMessage

    from expense_tracker.ui.runtime import HostRuntime
    from tests.fakes import ScriptedChatModel

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
                        "id": "c1",
                    }
                ],
            ),
            AIMessage(content="Done - I added ₹250 for lunch."),
        ]
    )
    runtime = HostRuntime(get_settings(), llm=llm).start()
    try:
        assert runtime.agent_ready
        monkeypatch.setattr(ui_app, "get_runtime", lambda: runtime)
        test = AppTest.from_function(_script, default_timeout=60).run()
        assert not test.exception
        assert not test.chat_input[0].disabled

        test.chat_input[0].set_value("add 250 for lunch").run()
        assert not test.exception, [e.value for e in test.exception]
        texts = [m.markdown[0].value for m in test.chat_message if m.markdown]
        assert "add 250 for lunch" in texts
        assert "Done - I added ₹250 for lunch." in texts
        assert any("1 tool call" in e.label for e in test.expander)

        # The agent's write is visible through the dashboard (same MCP server).
        assert len(runtime.call_tool("list_expenses", {"month": "2026-10"})) == 1
    finally:
        runtime.stop()


def test_new_chat_resets_history(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_core.messages import AIMessage

    from expense_tracker.ui.runtime import HostRuntime
    from tests.fakes import ScriptedChatModel

    runtime = HostRuntime(
        get_settings(), llm=ScriptedChatModel(script=[AIMessage(content="hello!")])
    ).start()
    try:
        monkeypatch.setattr(ui_app, "get_runtime", lambda: runtime)
        test = AppTest.from_function(_script, default_timeout=60).run()
        test.chat_input[0].set_value("hi").run()
        assert len(test.chat_message) == 2
        next(b for b in test.sidebar.button if "New chat" in b.label).click()
        test.run()
        assert len(test.chat_message) == 0
    finally:
        runtime.stop()
