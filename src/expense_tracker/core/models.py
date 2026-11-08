"""Database tables: expenses, durable user memory and audit events.

Table and column names are unchanged from v0.1, so existing ``expenses.db``
files remain compatible.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from expense_tracker.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_owner_date", "owner_id", "spent_on"),
        Index("ix_expenses_owner_category", "owner_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    category: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(String(240))
    spent_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MemoryItem(Base):
    __tablename__ = "memory_items"
    __table_args__ = (Index("ix_memory_owner_key", "owner_id", "memory_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_key: Mapped[str] = mapped_column(String(80))
    memory_value: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), default="preference")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
