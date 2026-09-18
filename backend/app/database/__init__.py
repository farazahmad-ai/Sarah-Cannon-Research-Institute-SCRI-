"""Database module for SCRI Oncology Copilot.

Exports base declarative classes, session engine, and SQLAlchemy ORM models.
"""

from app.database.base import Base, TimestampMixin
from app.database.models import (
    ChatMessage,
    ChatThread,
    ClinicalTrial,
    MessageCitation,
    Profile,
    TrialChunk,
)
from app.database.session import (
    async_session_factory,
    engine,
    get_db_session,
)

from app.database.supabase import (
    get_supabase_admin,
    init_supabase_admin,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "engine",
    "async_session_factory",
    "get_db_session",
    "init_supabase_admin",
    "get_supabase_admin",
    "Profile",
    "ClinicalTrial",
    "TrialChunk",
    "ChatThread",
    "ChatMessage",
    "MessageCitation",
]
