# Expense Tracker AI

An AI-native personal expense tracker built on the [Model Context Protocol](https://modelcontextprotocol.io).

- **MCP server** (FastMCP + SQLAlchemy + SQLite): expense CRUD, monthly summaries and durable memory, exposed as MCP tools, resources and prompts.
- **AI host** (LangChain + LangGraph): an agent that discovers the server's tools and answers questions about your spending.
- **Streamlit UI**: chat with the agent, a dashboard with charts and forms, and a memory editor — all going through the MCP server.

```
┌────────────────────────── AI host ──────────────────────────┐
│  Streamlit UI ──► HostRuntime ──► LangGraph agent ──► LLM   │
│  (ui/)            (background     (host/agent.py)  (OpenRouter)
│                    event loop)         │                    │
│                        └───────┬───────┘                    │
│                         ExpenseToolbox (one persistent      │
│                         MCP session, host/toolbox.py)       │
└────────────────────────────┬────────────────────────────────┘
                             │ MCP over STDIO (subprocess)
┌────────────────────────────▼────────────────────────────────┐
│  MCP server (mcp_server/)  ──►  core/ (repository, schemas) │
│                                        │                    │
│                                   SQLite (data/expenses.db) │
└─────────────────────────────────────────────────────────────┘
```

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"
cp .env.example .env                                   # then set OPENROUTER_API_KEY
expense-tracker-ui                                     # opens http://localhost:8501
```

The **dashboard and memory views work without an API key**; only the chat needs one.

| Command                 | What it runs                                          |
| ----------------------- | ----------------------------------------------------- |
| `expense-tracker-ui`    | Streamlit UI (extra args pass through to Streamlit)   |
| `expense-tracker-agent` | Terminal chat with the agent                          |
| `expense-tracker-mcp`   | The MCP server on its own, over STDIO (for any MCP host, e.g. Claude Desktop) |

Install only what you need: `pip install -e .` (server), `.[agent]` (+ agent), `.[ui]` (+ Streamlit).

### Use the server from another MCP host

```json
{
  "mcpServers": {
    "expense-tracker": {
      "command": "/path/to/.venv/bin/expense-tracker-mcp",
      "env": { "EXPENSE_DB_PATH": "/path/to/expenses.db" }
    }
  }
}
```

### Docker

```bash
docker build -t expense-tracker .
docker run -p 8501:8501 -v expense-data:/data --env-file .env expense-tracker
```

## Configuration

All settings are environment variables (a `.env` file is read automatically). See [`.env.example`](.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXPENSE_DB_PATH` | `./data/expenses.db` | SQLite file |
| `EXPENSE_USER_ID` | `local-demo` | Server-side data scope (not authentication) |
| `EXPENSE_LOG_LEVEL` | `INFO` | Log level (logs go to stderr) |
| `OPENROUTER_API_KEY` | – | Needed for chat |
| `OPENROUTER_MODEL` | `deepseek/deepseek-r1:free` | Any OpenRouter model id |
| `EXPENSE_LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `EXPENSE_MCP_PYTHON` | current interpreter | Python used to spawn the MCP server |

## MCP surface

- **Tools:** `add_expense`, `list_expenses`, `get_expense`, `update_expense`, `delete_expense`, `monthly_summary`, `remember_preference`, `recall_memory`, `search_memory`
- **Resources:** `expense://summary/{month}`, `expense://recent`, `memory://all`, `expense://database/schema`
- **Prompts:** `monthly_spending_review`, `spending_coach`

## Project layout

```
src/expense_tracker/
├── config.py            typed settings (pydantic-settings)
├── logging_config.py    stderr logging (stdout is reserved for MCP)
├── core/                domain layer: models, schemas, repository, memory, audit
├── mcp_server/          FastMCP server (tools / resources / prompts)
├── host/                AI host: toolbox, LLM factory, agent, chat service, CLI
└── ui/                  Streamlit app, async runtime bridge, formatting helpers
tests/
├── unit/                fast, no subprocesses
└── integration/         MCP server, AI host and UI (scripted LLM, no network)
```

More detail in [`docs/architecture.md`](docs/architecture.md).

## Development

```bash
make install     # editable install with all extras + pre-commit hooks
make check       # ruff + mypy --strict + pytest (what CI runs)
make format      # auto-fix
```

Tests never call a real LLM: the agent is exercised end-to-end with a scripted chat model against a real MCP subprocess and a temporary database.

## Security notes

This is a local, single-user project, not a hardened financial service.

- `EXPENSE_USER_ID` scopes data; it is **not** authentication. For multi-user use, derive the owner from a verified identity and keep enforcing ownership in every query.
- **The LLM cannot delete.** `delete_expense` is hidden from the agent (`DEFAULT_BLOCKED_TOOLS`). The UI offers deletion to the human behind an explicit confirmation. The tool also refuses to run without `confirm=true`.
- The MCP subprocess receives only `EXPENSE_*` variables, so LLM keys are never passed to it.
- No arbitrary-SQL tool is exposed. Don't store passwords, API keys or bank details in memory items (plain text in the DB).
- Never commit `.env`. For production add authentication, rate limits, secret management, backups and migrations (PostgreSQL + Alembic).

## License

MIT — see [LICENSE](LICENSE).
