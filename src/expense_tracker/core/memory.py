"""Durable, per-owner memory (preferences, goals, context)."""

from __future__ import annotations

from sqlalchemy import select

from expense_tracker.core.database import session_scope
from expense_tracker.core.exceptions import InputValidationError
from expense_tracker.core.models import MemoryItem
from expense_tracker.core.schemas import MEMORY_CATEGORIES

MAX_KEY_LENGTH = 80
MAX_VALUE_LENGTH = 2000


def _to_dict(row: MemoryItem) -> dict[str, str]:
    return {"key": row.memory_key, "value": row.memory_value, "category": row.category}


def remember(owner_id: str, key: str, value: str, category: str = "preference") -> dict[str, str]:
    """Upsert a memory item: the same key replaces the previous value."""
    key, value, category = key.strip().lower(), value.strip(), category.strip().lower()
    if not key or len(key) > MAX_KEY_LENGTH:
        raise InputValidationError(f"key must contain 1-{MAX_KEY_LENGTH} characters")
    if not value or len(value) > MAX_VALUE_LENGTH:
        raise InputValidationError(f"value must contain 1-{MAX_VALUE_LENGTH} characters")
    if category not in MEMORY_CATEGORIES:
        raise InputValidationError("category must be preference, goal, or context")
    with session_scope() as db:
        row = db.scalar(
            select(MemoryItem).where(MemoryItem.owner_id == owner_id, MemoryItem.memory_key == key)
        )
        if row:
            row.memory_value = value
            row.category = category
        else:
            row = MemoryItem(
                owner_id=owner_id, memory_key=key, memory_value=value, category=category
            )
            db.add(row)
        db.flush()
        return _to_dict(row)


def recall(owner_id: str, key: str | None = None) -> list[dict[str, str]]:
    """Return all memory items, or the one exact ``key``."""
    stmt = select(MemoryItem).where(MemoryItem.owner_id == owner_id)
    if key:
        stmt = stmt.where(MemoryItem.memory_key == key.strip().lower())
    stmt = stmt.order_by(MemoryItem.memory_key).limit(100)
    with session_scope() as db:
        return [_to_dict(r) for r in db.scalars(stmt).all()]


def find_memories(owner_id: str, query: str) -> list[dict[str, str]]:
    """Case-insensitive search over keys and values."""
    query = query.strip()
    if not query:
        raise InputValidationError("query cannot be blank")
    pattern = f"%{query[:100]}%"
    stmt = (
        select(MemoryItem)
        .where(
            MemoryItem.owner_id == owner_id,
            MemoryItem.memory_key.ilike(pattern) | MemoryItem.memory_value.ilike(pattern),
        )
        .order_by(MemoryItem.memory_key)
        .limit(20)
    )
    with session_scope() as db:
        return [_to_dict(r) for r in db.scalars(stmt).all()]
