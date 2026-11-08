"""Domain exceptions.

They subclass :class:`ValueError` so existing ``except ValueError`` handlers
(and MCP's error reporting) keep working.
"""

from __future__ import annotations


class ExpenseTrackerError(ValueError):
    """Base class for all domain errors."""


class InputValidationError(ExpenseTrackerError):
    """Input failed domain validation."""


class NotFoundError(ExpenseTrackerError):
    """The requested entity does not exist for this owner."""


class ConfirmationRequiredError(ExpenseTrackerError):
    """A destructive operation was requested without explicit confirmation."""
