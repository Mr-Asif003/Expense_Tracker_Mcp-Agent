"""Streamlit UI for the Expense Tracker AI host.

Run with ``expense-tracker-ui`` (or ``streamlit run src/expense_tracker/ui/app.py``).

Views
-----
* **Chat**       talk to the LLM agent (needs ``OPENROUTER_API_KEY``)
* **Dashboard**  monthly totals, charts, add/delete expenses (works without an LLM key)
* **Memory**     saved preferences and goals

Every data operation goes through the MCP server's tools.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

import streamlit as st

from expense_tracker.config import get_settings
from expense_tracker.core.schemas import ALLOWED_CATEGORIES, MEMORY_CATEGORIES
from expense_tracker.host.exceptions import HostError, ToolCallError
from expense_tracker.logging_config import configure_logging
from expense_tracker.ui import formatting as fmt
from expense_tracker.ui.runtime import HostRuntime

VIEWS = ("💬 Chat", "📊 Dashboard", "🧠 Memory")
SUGGESTIONS = (
    "Add ₹250 for lunch today under food",
    "Summarize my spending this month",
    "What did I spend on transport recently?",
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Resources & state
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Starting the MCP server…")
def get_runtime() -> HostRuntime:
    """One MCP session + agent per Streamlit server process."""
    configure_logging(get_settings().log_level)
    return HostRuntime().start()


def init_state() -> None:
    st.session_state.setdefault("thread_id", f"ui-{uuid.uuid4().hex[:12]}")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("flash", None)


def flash(kind: str, message: str) -> None:
    """Queue a message to show after the next rerun."""
    st.session_state["flash"] = (kind, message)


def show_flash() -> None:
    if st.session_state.get("flash"):
        kind, message = st.session_state.pop("flash")
        getattr(st, kind)(message)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar(rt: HostRuntime) -> tuple[str, str]:
    """Render the sidebar and return ``(view, month_key)``."""
    with st.sidebar:
        st.title("💸 Expense Tracker")
        st.caption("AI host · MCP · Streamlit")
        view = st.radio("View", VIEWS, label_visibility="collapsed")

        st.divider()
        today = date.today()
        st.subheader("Month")
        year_col, month_col = st.columns([1, 1.4])
        year = year_col.number_input("Year", 2000, 2100, today.year, step=1)
        month_name = month_col.selectbox("Month", fmt.MONTH_NAMES, index=today.month - 1)
        month = fmt.month_key(int(year), fmt.MONTH_NAMES.index(month_name) + 1)

        st.divider()
        if rt.connected:
            st.success("MCP server connected", icon="✅")
        if rt.agent_ready:
            st.success(f"Agent ready · {get_settings().openrouter_model}", icon="🤖")
        elif rt.connected:
            st.warning("Agent unavailable (dashboard still works)", icon="⚠️")

        if st.button("🗑️ New chat", width="stretch"):
            st.session_state["messages"] = []
            st.session_state["thread_id"] = f"ui-{uuid.uuid4().hex[:12]}"
            st.rerun()

        with st.expander("Tools"):
            blocked = sorted(set(rt.tool_names) - set(rt.agent_tool_names))
            st.markdown("\n".join(f"- `{name}`" for name in rt.agent_tool_names))
            if blocked:
                st.caption("Hidden from the AI: " + ", ".join(f"`{b}`" for b in blocked))
    return view, month


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
def render_tool_calls(tool_calls: list[dict[str, object]]) -> None:
    if not tool_calls:
        return
    with st.expander(f"🔧 {len(tool_calls)} tool call(s)"):
        for call in tool_calls:
            st.markdown(f"**`{call['name']}`**")
            st.json(call["arguments"], expanded=False)
            if call.get("result"):
                st.code(str(call["result"])[:1500], language="json")


def render_chat(rt: HostRuntime) -> None:
    st.header("Chat")
    if not rt.agent_ready:
        st.info(rt.agent_error or "The AI agent is not available.", icon="🔑")

    messages: list[dict[str, object]] = st.session_state["messages"]
    if not messages and rt.agent_ready:
        st.caption("Try one of these:")
        cols = st.columns(len(SUGGESTIONS))
        for col, text in zip(cols, SUGGESTIONS, strict=True):
            if col.button(text, width="stretch"):
                st.session_state["pending_prompt"] = text
                st.rerun()

    for message in messages:
        with st.chat_message(str(message["role"])):
            st.markdown(str(message["content"]))
            render_tool_calls(message.get("tool_calls", []))  # type: ignore[arg-type]

    prompt = st.chat_input("Ask about your expenses…", disabled=not rt.agent_ready)
    prompt = prompt or st.session_state.pop("pending_prompt", None)
    if not prompt:
        return

    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking…"):
                reply = rt.chat(st.session_state["thread_id"], prompt)
        except HostError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            logger.exception("Chat request failed")
            st.error(f"The request failed ({type(exc).__name__}). Check the server log.")
            return
        st.markdown(reply.text)
        calls: list[dict[str, object]] = [
            {"name": t.name, "arguments": t.arguments, "result": t.result} for t in reply.tool_calls
        ]
        render_tool_calls(calls)
    messages.append({"role": "assistant", "content": reply.text, "tool_calls": calls})


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def render_add_form(rt: HostRuntime) -> None:
    with (
        st.expander("Add an expense", icon=":material/add:"),
        st.form("add_expense", clear_on_submit=True),
    ):
        c1, c2 = st.columns(2)
        amount = c1.number_input(
            "Amount (₹)", min_value=0.01, value=100.0, step=10.0, format="%.2f"
        )
        category = c2.selectbox("Category", sorted(ALLOWED_CATEGORIES))
        description = st.text_input("Description", max_chars=240)
        spent_on = st.date_input("Date", value=date.today())
        if st.form_submit_button("Add expense", type="primary"):
            try:
                rt.call_tool(
                    "add_expense",
                    {
                        "amount": amount,
                        "category": category,
                        "description": description,
                        "spent_on": spent_on.isoformat(),
                    },
                )
            except ToolCallError as exc:
                st.error(str(exc))
            else:
                flash("success", "Expense added.")
                st.rerun()


def render_delete_form(rt: HostRuntime, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with st.expander("🗑️ Delete an expense"):
        labels = {
            int(r["id"]): f"#{r['id']} · {r['spent_on']} · {r['description']} · ₹{r['amount']}"  # type: ignore[call-overload]
            for r in rows
        }
        chosen = st.selectbox("Expense", list(labels), format_func=labels.__getitem__)
        confirmed = st.checkbox("I understand this cannot be undone")
        if st.button("Delete", disabled=not confirmed):
            try:
                # Deletion is a human decision made here; the LLM cannot reach this tool.
                rt.call_tool("delete_expense", {"expense_id": chosen, "confirm": True})
            except ToolCallError as exc:
                st.error(str(exc))
            else:
                flash("success", f"Deleted expense #{chosen}.")
                st.rerun()


def render_dashboard(rt: HostRuntime, month: str) -> None:
    st.header(f"Dashboard · {month}")
    show_flash()
    try:
        summary = rt.call_tool("monthly_summary", {"month": month})
        rows = rt.call_tool("list_expenses", {"month": month, "limit": 200})
    except ToolCallError as exc:
        st.error(str(exc))
        return

    top = fmt.top_category(summary)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total spent", summary["total"])
    m2.metric("Transactions", summary["transaction_count"])
    m3.metric(
        "Top category",
        top[0].title() if top else "—",
        top[1] if top else None,
        delta_color="off",
        delta_arrow="off",
    )

    if not rows:
        st.info("No expenses recorded for this month yet.")
        render_add_form(rt)
        return

    expenses = fmt.expenses_to_frame(rows)
    left, right = st.columns(2)
    with left:
        st.subheader("By category")
        st.bar_chart(fmt.category_frame(summary), y="amount", horizontal=True)
    with right:
        st.subheader("By day")
        st.bar_chart(fmt.daily_frame(expenses), y="amount")

    st.subheader("Transactions")
    if len(rows) >= 200:
        st.warning("Showing the 200 most recent transactions; totals above cover the whole month.")
    st.dataframe(
        expenses,
        hide_index=True,
        width="stretch",
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "amount": st.column_config.NumberColumn("Amount", format="₹%.2f"),
        },
    )
    render_add_form(rt)
    render_delete_form(rt, rows)


# --------------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------------- #
def render_memory(rt: HostRuntime) -> None:
    st.header("Memory")
    st.caption(
        "Preferences and goals the assistant can recall. "
        "Don't store passwords, API keys or bank details here."
    )
    show_flash()
    try:
        items = rt.call_tool("recall_memory")
    except ToolCallError as exc:
        st.error(str(exc))
        return

    if items:
        st.dataframe(items, hide_index=True, width="stretch")
    else:
        st.info("Nothing saved yet.")

    with st.form("remember", clear_on_submit=True):
        key = st.text_input("Key", placeholder="monthly_budget", max_chars=80)
        value = st.text_area("Value", placeholder="₹15000", max_chars=2000)
        category = st.selectbox("Category", sorted(MEMORY_CATEGORIES))
        if st.form_submit_button("Save", type="primary"):
            try:
                rt.call_tool(
                    "remember_preference", {"key": key, "value": value, "category": category}
                )
            except ToolCallError as exc:
                st.error(str(exc))
            else:
                flash("success", "Saved.")
                st.rerun()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title="Expense Tracker AI", page_icon="💸", layout="wide")
    init_state()
    rt = get_runtime()

    if rt.startup_error is not None:
        st.error(f"Could not start the MCP server: {rt.startup_error}")
        st.caption(
            "Check `EXPENSE_MCP_PYTHON` and that the package is installed (`pip install -e .[ui]`)."
        )
        # Drop the cached runtime so the next rerun retries instead of failing forever.
        if st.button("Retry"):
            get_runtime.clear()
            st.rerun()
        st.stop()

    view, month = render_sidebar(rt)
    if view == VIEWS[0]:
        render_chat(rt)
    elif view == VIEWS[1]:
        render_dashboard(rt, month)
    else:
        render_memory(rt)


if __name__ == "__main__":  # Streamlit executes the script as __main__
    main()
