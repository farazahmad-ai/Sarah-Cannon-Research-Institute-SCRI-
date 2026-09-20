"""FastAPI routes for chat threads, message history, and streaming completions.

Provides:
- POST /api/chat/threads: Create new screening thread.
- GET /api/chat/threads: List user screening threads.
- DELETE /api/chat/threads/{thread_id}: Delete screening thread.
- GET /api/chat/threads/{thread_id}/messages: Fetch thread message history.
- POST /api/chat/stream: Streaming response yielding Vercel AI SDK text frames.
"""

from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import ChatRequest, MessageOut, ThreadCreate, ThreadOut
from app.auth.jwt import AuthenticatedUser, get_current_user
from app.chat.orchestrator import stream_chat_turn
from app.database.chats import (
    create_thread,
    delete_thread,
    get_thread,
    list_messages,
    list_threads,
    upsert_profile,
)
from app.database.session import async_session_factory, get_db_session

chat_router = APIRouter(prefix="/chat", tags=["Chat"])


@chat_router.post(
    "/threads",
    response_model=ThreadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new screening thread",
)
async def create_new_thread(
    payload: ThreadCreate | None = None,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadOut:
    """Create a new clinical screening chat thread for the authenticated user."""
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id
    await upsert_profile(db, user_uuid, user.email)

    title = payload.title if payload and payload.title else "New Screening Session"
    thread = await create_thread(db, user_uuid, title=title)
    return ThreadOut.model_validate(thread)


@chat_router.get(
    "/threads",
    response_model=List[ThreadOut],
    summary="List all user screening threads",
)
async def get_user_threads(
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> List[ThreadOut]:
    """Return all screening threads belonging to the authenticated coordinator."""
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id
    threads = await list_threads(db, user_uuid)
    return [ThreadOut.model_validate(t) for t in threads]


@chat_router.delete(
    "/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a screening thread",
)
async def remove_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Delete a screening thread and its message cascade after ownership check."""
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id
    try:
        await delete_thread(db, thread_id, user_uuid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@chat_router.get(
    "/threads/{thread_id}/messages",
    response_model=List[MessageOut],
    summary="Get thread message history",
)
async def get_thread_messages(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user),
) -> List[MessageOut]:
    """Return chronological message turns for a thread after ownership check."""
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id
    try:
        messages = await list_messages(db, thread_id, user_uuid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return [MessageOut.model_validate(m) for m in messages]


@chat_router.post(
    "/stream",
    summary="Stream assistant completion for a chat turn",
)
async def chat_stream(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> StreamingResponse:
    """Stream token deltas in Vercel AI SDK data-stream format.

    No DB session is held during the SSE stream (D-4). The orchestrator opens
    and closes its own short-lived sessions.

    If request.thread_id is supplied, ownership is pre-validated in a short-lived
    session before starting the stream, ensuring 404/403 errors are returned as
    proper HTTP status codes rather than an aborted stream (R-5).
    """
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id

    if request.thread_id is not None:
        async with async_session_factory() as session:
            try:
                await get_thread(session, request.thread_id, user_uuid)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc
            except PermissionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(exc),
                ) from exc

    return StreamingResponse(
        stream_chat_turn(user, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
