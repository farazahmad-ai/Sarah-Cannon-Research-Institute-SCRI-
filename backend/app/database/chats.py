"""Database CRUD operations for clinical screening threads and messages.

Enforces:
- Profile bootstrap: Ensures a user profile exists before creating threads.
- Tenancy verification: Users can only read, write, or delete their own threads.
- Unified persistence: User prompt and assistant stream are committed together.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChatMessage, ChatThread, Profile


def _normalize_uuid(val: uuid.UUID | str) -> uuid.UUID:
    """Helper to ensure user_id or thread_id is a valid UUID instance."""
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


async def upsert_profile(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    email: str,
) -> None:
    """Ensure a profile record exists for the authenticated user.
    
    Prevents foreign key violations when creating chat threads for newly
    signed-in users whose profiles have not yet been explicitly seeded.
    """
    uid = _normalize_uuid(user_id)
    stmt = (
        insert(Profile)
        .values(id=uid, email=email, role="coordinator")
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(stmt)
    await session.flush()


async def create_thread(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    title: str = "New Screening Session",
) -> ChatThread:
    """Create a new clinical screening chat thread."""
    uid = _normalize_uuid(user_id)
    thread = ChatThread(
        user_id=uid,
        title=title,
    )
    session.add(thread)
    await session.flush()
    await session.refresh(thread)
    return thread


async def list_threads(
    session: AsyncSession,
    user_id: uuid.UUID | str,
) -> list[ChatThread]:
    """Return all chat threads belonging to the user, newest first."""
    uid = _normalize_uuid(user_id)
    stmt = (
        select(ChatThread)
        .where(ChatThread.user_id == uid)
        .order_by(ChatThread.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_thread(
    session: AsyncSession,
    thread_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
) -> ChatThread:
    """Retrieve a single thread with strict ownership enforcement.
    
    Raises:
        ValueError: If thread does not exist.
        PermissionError: If thread belongs to another user (tenancy violation).
    """
    tid = _normalize_uuid(thread_id)
    uid = _normalize_uuid(user_id)

    stmt = select(ChatThread).where(ChatThread.id == tid)
    result = await session.execute(stmt)
    thread = result.scalar_one_or_none()

    if thread is None:
        raise ValueError(f"Chat thread {tid} not found.")

    if thread.user_id != uid:
        raise PermissionError("Access denied: thread belongs to another coordinator.")

    return thread


async def delete_thread(
    session: AsyncSession,
    thread_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
) -> None:
    """Delete a screening thread and all cascade-related messages and citations."""
    thread = await get_thread(session, thread_id, user_id)
    await session.delete(thread)
    await session.flush()


async def list_messages(
    session: AsyncSession,
    thread_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
) -> list[ChatMessage]:
    """Fetch chronological message history for a thread, enforcing tenancy."""
    # Enforces ownership check; raises ValueError or PermissionError if invalid
    await get_thread(session, thread_id, user_id)
    tid = _normalize_uuid(thread_id)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == tid)
        .order_by(ChatMessage.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def persist_turn(
    session: AsyncSession,
    thread_id: uuid.UUID | str,
    user_content: str,
    assistant_content: str,
) -> tuple[ChatMessage, ChatMessage]:
    """Persist both user query and assistant response in a single transaction."""
    tid = _normalize_uuid(thread_id)
    user_msg = ChatMessage(
        thread_id=tid,
        role="user",
        content=user_content,
    )
    assistant_msg = ChatMessage(
        thread_id=tid,
        role="assistant",
        content=assistant_content,
    )
    session.add_all([user_msg, assistant_msg])
    await session.flush()
    await session.refresh(user_msg)
    await session.refresh(assistant_msg)
    return user_msg, assistant_msg
