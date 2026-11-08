from decimal import Decimal

import pytest

from expense_tracker.ui import formatting as fmt


@pytest.mark.parametrize(
    ("text", "expected"), [("₹1,234.50", "1234.50"), ("99", "99"), (" ₹0.00 ", "0.00")]
)
def test_parse_money(text: str, expected: str) -> None:
    assert fmt.parse_money(text) == Decimal(expected)


def test_parse_money_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        fmt.parse_money("lots")


def test_format_inr() -> None:
    assert fmt.format_inr(Decimal("1234.5")) == "₹1,234.50"


def test_month_key() -> None:
    assert fmt.month_key(2026, 3) == "2026-03"


ROWS = [
    {"id": 2, "amount": "50.00", "category": "food", "description": "b", "spent_on": "2026-10-02"},
    {"id": 1, "amount": "25.50", "category": "food", "description": "a", "spent_on": "2026-10-02"},
    {
        "id": 3,
        "amount": "10.00",
        "category": "travel",
        "description": "c",
        "spent_on": "2026-10-03",
    },
]


def test_expenses_to_frame_and_daily_totals() -> None:
    frame = fmt.expenses_to_frame(ROWS)
    assert list(frame.columns) == fmt.EXPENSE_COLUMNS
    daily = fmt.daily_frame(frame)
    assert daily["amount"].tolist() == [75.5, 10.0]


def test_empty_frames() -> None:
    frame = fmt.expenses_to_frame([])
    assert frame.empty
    assert fmt.daily_frame(frame).empty


def test_category_frame_and_top_category() -> None:
    summary = {"by_category": {"food": "₹1,075.50", "travel": "₹2,000.00"}}
    assert fmt.category_frame(summary)["amount"].tolist() == [1075.5, 2000.0]
    assert fmt.top_category(summary) == ("travel", "₹2,000.00")
    assert fmt.top_category({"by_category": {}}) is None
