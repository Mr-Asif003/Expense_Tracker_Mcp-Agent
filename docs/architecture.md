# Architecture

## Layers

| Layer | Package | Depends on | Responsibility |
| --- | --- | --- | --- |
| Domain | `expense_tracker.core` | SQLAlchemy, pydantic | Models, validation, repositories. No MCP/LLM/UI code. |
| MCP server | `expense_tracker.mcp_server` | `core` | Adapts the domain to MCP tools/resources/prompts; converts domain errors to clean `ToolError`s. |
| AI host | `expense_tracker.host` | MCP (over STDIO only) | Connects to the server, builds the LangGraph agent, runs chat turns. |
| UI | `expense_tracker.ui` | `host` | Streamlit front-end. |

The dependency direction is one-way: `ui → host → (MCP protocol) → mcp_server → core`. The host never imports the server or the repository; it only speaks MCP, so the server can be swapped for any other MCP server exposing the same tools. (The UI imports the category lists from `core.schemas` purely to populate dropdowns.)

## Key design decisions

**One persistent MCP session.** The original agent spawned a new server subprocess for every tool call (~1.5 s each). `ExpenseToolbox` holds one session open for the life of the process, so calls take milliseconds and share state.

**Streamlit ↔ asyncio bridge.** Streamlit re-executes the script on every interaction, while the MCP session and LangGraph agent need a long-lived event loop. `HostRuntime` runs a daemon thread with its own loop that owns both; the UI calls into it synchronously. It is created once with `st.cache_resource`.

**UI works without an LLM.** Dashboard/memory views call MCP tools directly through `ExpenseToolbox.call`, so a missing API key disables only the chat.

**Destructive tools are human-only.** `delete_expense` is filtered out of `agent_tools`. The UI calls it directly after a confirmation checkbox.

**Money is integers.** Amounts are stored as integer paise, converted with `Decimal` and half-up rounding; no binary floats in storage.

**Summaries are aggregated in SQL.** Totals use `GROUP BY`, so they stay correct beyond any list limit.

**No import-time side effects.** Settings, engine and directories are created lazily; logging goes to stderr only, because STDIO MCP uses stdout for protocol frames.

**Minimal subprocess environment.** The server subprocess receives only `EXPENSE_*` variables.

## Data model

`expenses`, `memory_items`, `audit_events` (see `core/models.py`). Table and column names are unchanged from v0.1, so existing databases keep working. There is no migration tool yet; add Alembic before changing the schema.
