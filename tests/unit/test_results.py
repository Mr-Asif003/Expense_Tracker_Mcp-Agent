import pytest

from expense_tracker.host.exceptions import ToolCallError
from expense_tracker.host.results import content_to_text, parse_tool_result


def test_content_to_text_handles_blocks() -> None:
    blocks = [{"type": "text", "text": "a"}, {"type": "image", "x": 1}, "b"]
    assert content_to_text(blocks) == "ab"
    assert content_to_text("plain") == "plain"
    assert content_to_text(None) == ""


def test_parse_json_payload() -> None:
    assert parse_tool_result([{"type": "text", "text": '{"a": 1}'}]) == {"a": 1}


def test_parse_non_json_returns_text() -> None:
    assert parse_tool_result("hello") == "hello"


def test_parse_error_raises() -> None:
    with pytest.raises(ToolCallError, match="Expense not found"):
        parse_tool_result("Error calling tool 'get_expense': Expense not found")
