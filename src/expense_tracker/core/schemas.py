"""Input validation and money helpers shared by every interface."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from expense_tracker.core.exceptions import InputValidationError

CURRENCY = "INR"
MAX_AMOUNT = Decimal("10000000")
ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "food",
        "transport",
        "housing",
        "utilities",
        "health",
        "shopping",
        "education",
        "entertainment",
        "travel",
        "other",
    }
)
MEMORY_CATEGORIES: frozenset[str] = frozenset({"preference", "goal", "context"})


def normalize_category(value: str) -> str:
    """Lower-case/strip and verify membership in :data:`ALLOWED_CATEGORIES`."""
    value = value.strip().lower()
    if value not in ALLOWED_CATEGORIES:
        raise InputValidationError(
            f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}"
        )
    return value


def normalize_description(value: str) -> str:
    value = value.strip()
    if not value:
        raise InputValidationError("description cannot be blank")
    return value


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=MAX_AMOUNT, description="Amount in INR")
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=240)
    spent_on: date

    _category = field_validator("category")(normalize_category)
    _description = field_validator("description")(normalize_description)


class ExpenseUpdate(BaseModel):
    """Partial update; at least one field must be supplied."""

    amount: Decimal | None = Field(default=None, gt=0, le=MAX_AMOUNT)
    category: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, min_length=1, max_length=240)
    spent_on: date | None = None

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str | None) -> str | None:
        return None if value is None else normalize_category(value)

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str | None) -> str | None:
        return None if value is None else normalize_description(value)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if all(v is None for v in (self.amount, self.category, self.description, self.spent_on)):
            raise InputValidationError("Provide at least one field to update")
        return self


def to_paise(amount: Decimal | str | int | float) -> int:
    """Convert rupees to integer paise, avoiding binary-float storage."""
    try:
        value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise InputValidationError("amount must be a valid number") from exc
    if value <= 0:
        raise InputValidationError("amount must be greater than zero")
    if value > MAX_AMOUNT:
        raise InputValidationError("amount exceeds the configured maximum")
    return int(value * 100)


def paise_to_decimal(paise: int) -> Decimal:
    return Decimal(paise) / Decimal(100)


def money_from_paise(paise: int) -> str:
    return f"₹{paise_to_decimal(paise):,.2f}"


def month_range(month: str) -> tuple[date, date]:
    """Return the half-open ``[start, end)`` date range for a ``YYYY-MM`` string."""
    try:
        year_text, month_text = month.split("-")
        year, mon = int(year_text), int(month_text)
        if not 1 <= mon <= 12:
            raise ValueError
        start = date(year, mon, 1)
        end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    except (ValueError, TypeError) as exc:
        raise InputValidationError("month must use YYYY-MM format") from exc
    return start, end
