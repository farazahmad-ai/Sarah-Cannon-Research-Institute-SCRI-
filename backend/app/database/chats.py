"""Database CRUD operations for clinical screening threads and messages.

Enforces:
- Profile bootstrap: Ensures a user profile exists before creating threads.
- Tenancy verification: Users can only read, write, or delete their own threads.
- Unified persistence: User prompt and assistant stream are committed together.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assistant.schemas import MessageCitationCreate
from app.database.models import ChatMessage, ChatThread, MessageCitation, Profile


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
    Handles existing records safely to avoid unique constraint collisions.
    """
    uid = _normalize_uuid(user_id)
    existing = await session.get(Profile, uid)
    if existing:
        if existing.email != email:
            existing.email = email
            await session.flush()
        return

    # Check if a profile with this email already exists under another id
    res = await session.execute(select(Profile).where(Profile.email == email))
    by_email = res.scalar_one_or_none()
    if by_email:
        return

    profile = Profile(id=uid, email=email, role="coordinator")
    session.add(profile)
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
    """Fetch chronological message history for a thread, enforcing tenancy.

    Eagerly loads message citations ordered by citation_index for one-click audit.
    """
    # Enforces ownership check; raises ValueError or PermissionError if invalid
    await get_thread(session, thread_id, user_id)
    tid = _normalize_uuid(thread_id)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == tid)
        .options(selectinload(ChatMessage.citations))
        .order_by(ChatMessage.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def persist_turn(
    session: AsyncSession,
    thread_id: uuid.UUID | str,
    user_content: str,
    assistant_content: str,
    citations: list[MessageCitationCreate] | None = None,
) -> tuple[ChatMessage, ChatMessage]:
    """Persist user query, assistant response, and verified citations in a single transaction."""
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

    if citations:
        citation_records = [
            MessageCitation(
                message_id=assistant_msg.id,
                chunk_id=c.chunk_id,
                nct_id=c.nct_id,
                section_header=c.section_header,
                verbatim_quote=c.verbatim_quote,
                citation_index=c.citation_index,
                last_update_posted_date=c.last_update_posted_date,
            )
            for c in citations
        ]
        session.add_all(citation_records)
        await session.flush()

    await session.refresh(user_msg)
    await session.refresh(assistant_msg, attribute_names=["citations"])
    return user_msg, assistant_msg


async def record_message_feedback(
    session: AsyncSession,
    message_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    rating: str,
    comment: str | None = None,
) -> ChatMessage:
    """Record coordinator feedback on an assistant message with tenancy verification."""
    mid = _normalize_uuid(message_id)
    uid = _normalize_uuid(user_id)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.id == mid)
        .options(selectinload(ChatMessage.citations))
    )
    result = await session.execute(stmt)
    message = result.scalar_one_or_none()

    if message is None:
        raise ValueError(f"Chat message {mid} not found.")

    # Ownership check via thread relationship
    thread_res = await session.execute(
        select(ChatThread.user_id).where(ChatThread.id == message.thread_id)
    )
    owner_id = thread_res.scalar_one_or_none()
    if owner_id != uid:
        raise PermissionError("Access denied: message belongs to another coordinator's thread.")

    meta = dict(message.metadata_json or {})
    meta["feedback"] = {
        "rating": rating,
        "comment": comment,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    message.metadata_json = meta
    await session.flush()
    await session.refresh(message, attribute_names=["citations"])
    return message


