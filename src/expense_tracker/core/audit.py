"""Audit-trail helper."""

from __future__ import annotations

from sqlalchemy.orm import Session

from expense_tracker.core.models import AuditEvent


def record(
    db: Session,
    owner_id: str,
    action: str,
    entity_type: str,
    entity_id: int | str,
    details: str = "",
) -> None:
    """Add an audit event to the current transaction."""
    db.add(
        AuditEvent(
            owner_id=owner_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details,
        )
    )
