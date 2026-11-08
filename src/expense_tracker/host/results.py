"""Helpers for normalising LangChain message content and MCP tool results."""

from __future__ import annotations

import json
from typing import Any

from expense_tracker.host.exceptions import ToolCallError

_ERROR_PREFIX = "Error calling tool"


def content_to_text(content: Any) -> str:
    """Flatten LangChain message/tool content (``str`` or content blocks) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def parse_tool_result(raw: Any) -> Any:
    """Return the JSON payload of an MCP tool result, or its text if not JSON.

    Raises:
        ToolCallError: if the tool reported an error.
    """
    text = content_to_text(raw).strip()
    if text.startswith(_ERROR_PREFIX):
        # "Error calling tool 'x': message" -> "message"
        _, _, message = text.partition("': ")
        raise ToolCallError(message or text)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
