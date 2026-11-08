"""Expense persistence. No MCP or LLM-specific code belongs here.

Every query is scoped to ``owner_id``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select

from expense_tracker.core import audit
from expense_tracker.core.database import session_scope
from expense_tracker.core.exceptions import (
    ConfirmationRequiredError,
    InputValidationError,
    NotFoundError,
)
from expense_tracker.core.models import Expense
from expense_tracker.core.schemas import (
    CURRENCY,
    ExpenseCreate,
    ExpenseUpdate,
    money_from_paise,
    month_range,
    normalize_category,
    paise_to_decimal,
    to_paise,
)

MAX_LIST_LIMIT = 200


def _to_dict(row: Expense) -> dict[str, Any]:
    return {
        "id": row.id,
        "amount": f"{paise_to_decimal(row.amount_paise):.2f}",
        "currency": row.currency,
        "category": row.category,
        "description": row.description,
        "spent_on": row.spent_on.isoformat(),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _owned(owner_id: str, expense_id: int) -> Any:
    return select(Expense).where(Expense.id == expense_id, Expense.owner_id == owner_id)


def create_expense(owner_id: str, payload: ExpenseCreate) -> dict[str, Any]:
    with session_scope() as db:
        row = Expense(
            owner_id=owner_id,
            amount_paise=to_paise(payload.amount),
            currency=CURRENCY,
            category=payload.category,
            description=payload.description,
            spent_on=payload.spent_on,
        )
        db.add(row)
        db.flush()
        audit.record(db, owner_id, "create", "expense", row.id, payload.description)
        db.flush()
        db.refresh(row)
        return _to_dict(row)


def list_expenses(
    owner_id: str,
    month: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= MAX_LIST_LIMIT:
        raise InputValidationError(f"limit must be between 1 and {MAX_LIST_LIMIT}")
    stmt = select(Expense).where(Expense.owner_id == owner_id)
    if month:
        start, end = month_range(month)
        stmt = stmt.where(Expense.spent_on >= start, Expense.spent_on < end)
    if category:
        stmt = stmt.where(Expense.category == normalize_category(category))
    stmt = stmt.order_by(desc(Expense.spent_on), desc(Expense.id)).limit(limit)
    with session_scope() as db:
        return [_to_dict(row) for row in db.scalars(stmt).all()]


def get_expense(owner_id: str, expense_id: int) -> dict[str, Any]:
    with session_scope() as db:
        row = db.scalar(_owned(owner_id, expense_id))
        if row is None:
            raise NotFoundError("Expense not found")
        return _to_dict(row)


def update_expense(owner_id: str, expense_id: int, changes: ExpenseUpdate) -> dict[str, Any]:
    with session_scope() as db:
        row = db.scalar(_owned(owner_id, expense_id))
        if row is None:
            raise NotFoundError("Expense not found")
        changed: list[str] = []
        if changes.amount is not None:
            row.amount_paise = to_paise(changes.amount)
            changed.append("amount")
        if changes.category is not None:
            row.category = changes.category
            changed.append("category")
        if changes.description is not None:
            row.description = changes.description
            changed.append("description")
        if changes.spent_on is not None:
            row.spent_on = changes.spent_on
            changed.append("spent_on")
        audit.record(db, owner_id, "update", "expense", row.id, ",".join(changed))
        db.flush()
        db.refresh(row)
        return _to_dict(row)


def delete_expense(owner_id: str, expense_id: int, confirm: bool) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequiredError(
            "Deletion not performed. Set confirm=true only after the user explicitly confirms."
        )
    with session_scope() as db:
        row = db.scalar(_owned(owner_id, expense_id))
        if row is None:
            raise NotFoundError("Expense not found")
        description = row.description
        audit.record(db, owner_id, "delete", "expense", row.id, description)
        db.delete(row)
        return {"deleted": True, "expense_id": expense_id, "description": description}


def expense_summary(owner_id: str, month: str) -> dict[str, Any]:
    """Aggregate in SQL so the result is correct for any number of transactions."""
    start, end = month_range(month)
    stmt = (
        select(Expense.category, func.sum(Expense.amount_paise), func.count(Expense.id))
        .where(Expense.owner_id == owner_id, Expense.spent_on >= start, Expense.spent_on < end)
        .group_by(Expense.category)
        .order_by(Expense.category)
    )
    with session_scope() as db:
        rows = db.execute(stmt).all()
    total = sum(int(paise) for _, paise, _ in rows)
    return {
        "month": month,
        "transaction_count": sum(int(count) for _, _, count in rows),
        "total": money_from_paise(total),
        "by_category": {category: money_from_paise(int(paise)) for category, paise, _ in rows},
        "note": "This is a summary of recorded expenses, not financial advice.",
    }
