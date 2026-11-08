"""Pure helpers that convert MCP tool payloads into display-ready data (no Streamlit)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


def parse_money(text: str) -> Decimal:
    """Parse ``"₹1,234.50"`` (or ``"1234.50"``) into a :class:`Decimal`."""
    cleaned = text.replace("₹", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Not a monetary amount: {text!r}") from exc


def format_inr(amount: Decimal | float | int) -> str:
    return f"₹{Decimal(str(amount)):,.2f}"


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


EXPENSE_COLUMNS = ["id", "date", "category", "description", "amount"]


def expenses_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert ``list_expenses`` output to a DataFrame with numeric amounts."""
    records = [
        {
            "id": row["id"],
            "date": date.fromisoformat(row["spent_on"]),
            "category": row["category"],
            "description": row["description"],
            "amount": float(parse_money(row["amount"])),
        }
        for row in rows
    ]
    return pd.DataFrame.from_records(records, columns=EXPENSE_COLUMNS)


def category_frame(summary: dict[str, Any]) -> pd.DataFrame:
    """Convert ``monthly_summary`` output to a ``category -> amount`` frame."""
    by_category = summary.get("by_category", {})
    return pd.DataFrame(
        {"amount": [float(parse_money(v)) for v in by_category.values()]},
        index=pd.Index(list(by_category), name="category"),
    )


def daily_frame(expenses: pd.DataFrame) -> pd.DataFrame:
    """Total spend per day, indexed by date."""
    if expenses.empty:
        return pd.DataFrame({"amount": []}, index=pd.Index([], name="date"))
    return expenses.groupby("date")[["amount"]].sum().sort_index()


def top_category(summary: dict[str, Any]) -> tuple[str, str] | None:
    """Return ``(category, formatted_amount)`` for the biggest category, if any."""
    by_category = summary.get("by_category", {})
    if not by_category:
        return None
    name = max(by_category, key=lambda c: parse_money(by_category[c]))
    return name, by_category[name]
