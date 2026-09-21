"""Database base class and declarative model mixins.

Provides:
- Base: Root declarative base for all SQLAlchemy ORM models with async support.
- TimestampMixin: Standard created_at and updated_at timezone-aware datetime mixin.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Root declarative base class for all SCRI Oncology Copilot models.
    
    AsyncAttrs enables lazy loading and attribute evaluation across async boundaries
    without triggering Greenlet / MissingGreenlet concurrency exceptions.
    """
    pass


class TimestampMixin:
    """Provides consistent timezone-aware audit timestamps for clinical records.
    
    Why this is critical:
    In oncology trial screening, audit trails are non-negotiable. We must track
    the exact moment a patient screening turn occurred, when protocol chunks were
    ingested, and when protocol amendments were posted.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
