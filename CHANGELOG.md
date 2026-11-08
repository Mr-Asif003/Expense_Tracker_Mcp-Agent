# Changelog

## 0.2.0

### Added
- **Streamlit UI** for the AI host: chat (with tool-call inspector), dashboard (metrics, charts, add/delete expense), memory editor.
- `pydantic-settings` based configuration, `.env.example`, structured stderr logging.
- Test suite (unit + integration), ruff, mypy `--strict`, pre-commit, GitHub Actions CI, Makefile, Dockerfile.

### Changed
- Merged `expense-tracker-mcp` and `expense-tracker-agent` into one `src`-layout package `expense_tracker` (`core`, `mcp_server`, `host`, `ui`) with proper imports and console scripts.
- The agent keeps one persistent MCP session instead of spawning a server per tool call.
- Server tool errors are returned as concise `ToolError` messages (no stack traces for validation errors).
- Only `EXPENSE_*` variables are forwarded to the MCP subprocess.
- Dependencies trimmed to what is used; optional extras `agent`, `ui`, `dev`.

### Fixed
- Monthly summary silently ignored transactions beyond the first 200; it now aggregates in SQL.
- `expense://database/schema` resource emitted a literal `\n` instead of newlines.
- Hard-coded `E:\...` paths and import-time `print`/`mkdir` side effects removed.
- Empty `OPENROUTER_API_KEY=` is now treated as "not set".

### Removed
- `EXPENSE_MCP_SRC` (the server is now an installed package launched with `python -m expense_tracker.mcp_server`).
- Unused OpenAI/Gemini/HF/Mongo settings and the committed `.env` / `*.db` / `__pycache__` / `egg-info` files.

### Migrating from 0.1
Point `EXPENSE_DB_PATH` at your existing `expenses.db`; the schema is unchanged. **Rotate any API keys that were stored in the old `.env` files.**
