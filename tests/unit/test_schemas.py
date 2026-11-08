from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from expense_tracker.core.exceptions import InputValidationError
from expense_tracker.core.schemas import (
    ExpenseCreate,
    ExpenseUpdate,
    money_from_paise,
    month_range,
    to_paise,
)


def test_rupees_convert_to_integer_paise() -> None:
    assert to_paise(Decimal("12.34")) == 1234


def test_float_amounts_do_not_drift() -> None:
    assert to_paise(0.1 + 0.2) == 30


def test_rounding_is_half_up() -> None:
    assert to_paise("1.005") == 101


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "10000000.01"])
def test_invalid_amounts_are_rejected(bad: str) -> None:
    with pytest.raises(InputValidationError):
        to_paise(bad)


def test_money_formatting() -> None:
    assert money_from_paise(123456) == "₹1,234.56"


def test_category_is_normalised() -> None:
    expense = ExpenseCreate(
        amount=10, category="  FOOD ", description=" tea ", spent_on=date.today()
    )
    assert (expense.category, expense.description) == ("food", "tea")


def test_invalid_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="category must be one of"):
        ExpenseCreate(amount=10, category="unrecognized", description="x", spent_on=date.today())


def test_blank_description_is_rejected() -> None:
    with pytest.raises(ValueError):
        ExpenseCreate(amount=10, category="food", description="   ", spent_on=date.today())


def test_update_requires_a_field() -> None:
    with pytest.raises(ValueError, match="at least one field"):
        ExpenseUpdate()


def test_update_rejects_bad_date() -> None:
    with pytest.raises(ValidationError):
        ExpenseUpdate(spent_on="31-12-2026")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("month", "start", "end"),
    [
        ("2026-10", date(2026, 10, 1), date(2026, 11, 1)),
        ("2026-12", date(2026, 12, 1), date(2027, 1, 1)),
    ],
)
def test_month_range(month: str, start: date, end: date) -> None:
    assert month_range(month) == (start, end)


@pytest.mark.parametrize("bad", ["2026", "2026-13", "2026-00", "abcd-ef", "2026-1-1"])
def test_month_range_rejects_bad_input(bad: str) -> None:
    with pytest.raises(InputValidationError):
        month_range(bad)
