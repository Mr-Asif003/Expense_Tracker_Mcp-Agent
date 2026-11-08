from datetime import date
from pathlib import Path

import pytest

from expense_tracker.core import repository
from expense_tracker.core.exceptions import (
    ConfirmationRequiredError,
    InputValidationError,
    NotFoundError,
)
from expense_tracker.core.schemas import ExpenseCreate, ExpenseUpdate

pytestmark = pytest.mark.usefixtures("db")


def _add(owner: str, amount: float = 100, category: str = "food", day: int = 5, month: int = 10):
    return repository.create_expense(
        owner,
        ExpenseCreate(
            amount=amount, category=category, description="item", spent_on=date(2026, month, day)
        ),
    )


def test_create_and_get(owner: str) -> None:
    created = _add(owner, 125.5)
    assert created["amount"] == "125.50"
    assert repository.get_expense(owner, created["id"]) == created


def test_list_filters_by_month_and_category(owner: str) -> None:
    _add(owner, category="food", month=10)
    _add(owner, category="travel", month=10)
    _add(owner, category="food", month=11)
    assert len(repository.list_expenses(owner, month="2026-10")) == 2
    assert len(repository.list_expenses(owner, month="2026-10", category="Food")) == 1


def test_list_is_newest_first(owner: str) -> None:
    _add(owner, day=1)
    _add(owner, day=9)
    assert [r["spent_on"] for r in repository.list_expenses(owner)] == ["2026-10-09", "2026-10-01"]


@pytest.mark.parametrize("limit", [0, 201])
def test_list_limit_is_validated(owner: str, limit: int) -> None:
    with pytest.raises(InputValidationError):
        repository.list_expenses(owner, limit=limit)


def test_owner_isolation(owner: str) -> None:
    created = _add(owner)
    assert repository.list_expenses("someone-else") == []
    with pytest.raises(NotFoundError):
        repository.get_expense("someone-else", created["id"])
    with pytest.raises(NotFoundError):
        repository.delete_expense("someone-else", created["id"], confirm=True)


def test_update_changes_only_given_fields(owner: str) -> None:
    created = _add(owner, 100, "food")
    updated = repository.update_expense(
        owner, created["id"], ExpenseUpdate(amount=150, category="travel")
    )
    assert (updated["amount"], updated["category"], updated["description"]) == (
        "150.00",
        "travel",
        "item",
    )


def test_update_missing_expense(owner: str) -> None:
    with pytest.raises(NotFoundError):
        repository.update_expense(owner, 999, ExpenseUpdate(amount=1))


def test_delete_requires_confirmation(owner: str) -> None:
    created = _add(owner)
    with pytest.raises(ConfirmationRequiredError):
        repository.delete_expense(owner, created["id"], confirm=False)
    assert repository.get_expense(owner, created["id"])  # still there
    assert repository.delete_expense(owner, created["id"], confirm=True)["deleted"] is True
    with pytest.raises(NotFoundError):
        repository.get_expense(owner, created["id"])


def test_summary_totals_by_category(owner: str) -> None:
    _add(owner, 100.25, "food")
    _add(owner, 50, "food")
    _add(owner, 20, "travel")
    _add(owner, 999, "food", month=11)  # other month, must be excluded
    summary = repository.expense_summary(owner, "2026-10")
    assert summary["transaction_count"] == 3
    assert summary["total"] == "₹170.25"
    assert summary["by_category"] == {"food": "₹150.25", "travel": "₹20.00"}


def test_summary_is_not_truncated_by_the_list_limit(owner: str) -> None:
    """Regression: v0.1 computed summaries from list_expenses(limit=200)."""
    for _ in range(205):
        _add(owner, 1)
    summary = repository.expense_summary(owner, "2026-10")
    assert summary["transaction_count"] == 205
    assert summary["total"] == "₹205.00"


def test_summary_of_empty_month(owner: str) -> None:
    summary = repository.expense_summary(owner, "2026-01")
    assert summary["transaction_count"] == 0
    assert summary["total"] == "₹0.00"
    assert summary["by_category"] == {}


def test_summary_rejects_bad_month(owner: str) -> None:
    with pytest.raises(InputValidationError):
        repository.expense_summary(owner, "oct-2026")


def test_audit_events_are_recorded(owner: str) -> None:
    from sqlalchemy import select

    from expense_tracker.core.database import session_scope
    from expense_tracker.core.models import AuditEvent

    created = _add(owner)
    repository.update_expense(owner, created["id"], ExpenseUpdate(amount=5))
    repository.delete_expense(owner, created["id"], confirm=True)
    with session_scope() as db:
        actions = [e.action for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id))]
    assert actions == ["create", "update", "delete"]


def test_importing_the_package_does_not_touch_the_filesystem(tmp_path: Path) -> None:
    import subprocess
    import sys

    target = tmp_path / "should-not-exist"
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import expense_tracker.core.database, expense_tracker.core.repository",
        ],
        env={"EXPENSE_DB_PATH": str(target / "x.db"), "PATH": ""},
        check=True,
    )
    assert not target.exists()
