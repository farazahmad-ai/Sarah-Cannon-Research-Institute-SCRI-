"""Streaming chat orchestrator for SCRI Oncology Copilot.

Orchestrates the chat turn pipeline:
1. Bootstraps user profile in database.
2. Resolves or creates the chat thread.
3. Retrieves relevant protocol passages (stubbed in this slice).
4. Assembles prompt with system instructions, conversation history, and protocol context.
5. Streams completions from OpenAI/OpenRouter in Vercel AI SDK data-stream format.
6. Persists the completed turn to the database in a unified transaction.
"""

from collections.abc import AsyncGenerator
import json
import logging
from typing import Any, Dict, List
import uuid

import openai
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import ChatRequest, ProtocolPassage
from app.auth.jwt import AuthenticatedUser
from app.config import settings
from app.database.chats import (
    create_thread,
    get_thread,
    list_messages,
    persist_turn,
    upsert_profile,
)
from app.database.models import ChatMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an intelligent clinical trial protocol assistant for Sarah Cannon Research Institute (SCRI). "
    "Your role is to assist clinical research coordinators in screening cancer patients against trial protocols. "
    "Answer questions strictly and solely using the provided protocol context. "
    "Always cite the protocol passage in bracketed format (e.g. [NCTxxxxxxx, Section Title]). "
    "If the provided protocol context does not contain the answer, explicitly state: 'The protocol does not state [X].' "
    "Never guess, extrapolate, or generalize from other medical literature."
)


def _stub_retrieve(message: str) -> ProtocolPassage:
    """Hardcoded single passage stub.
    
    Replaced by hybrid.retrieve() in Phase 4. Returns a realistic clinical
    exclusion criterion so the assistant demonstrates grounded citation behavior.
    """
    return ProtocolPassage(
        nct_id="NCT05794958",
        section_header="Eligibility: Exclusion Criterion #7",
        chunk_text=(
            "Prior anti-cancer therapy within 4 weeks before the first "
            "dose of study treatment, or 5 half-lives of the drug, "
            "whichever is shorter."
        ),
    )


def build_openai_messages(
    history: List[ChatMessage],
    passage: ProtocolPassage,
    user_message: str,
) -> List[Dict[str, str]]:
    """Assemble the OpenAI messages array for chat completion."""
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT,
    }
    prior = [{"role": m.role, "content": m.content} for m in history[-10:]]
    context_block = (
        f"[{passage.nct_id}, {passage.section_header}]\n{passage.chunk_text}"
    )
    user = {
        "role": "user",
        "content": f"Protocol Context:\n{context_block}\n\nQuestion: {user_message}",
    }
    return [system, *prior, user]


async def stream_chat_turn(
    db: AsyncSession,
    user: AuthenticatedUser,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Execute streaming chat turn and yield Vercel AI SDK formatted frames."""
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id

    # 1. Guarantee profile exists
    await upsert_profile(db, user_uuid, user.email)

    # 2. Get or create thread
    if request.thread_id is None:
        title = request.message.strip()[:60] or "New Screening Session"
        thread = await create_thread(db, user_uuid, title=title)
    else:
        thread = await get_thread(db, request.thread_id, user_uuid)

    # 3. Retrieve protocol passage (stub)
    passage = _stub_retrieve(request.message)

    # 4. Fetch conversation history
    history = await list_messages(db, thread.id, user_uuid)

    # 5. Build prompt messages
    messages = build_openai_messages(history, passage, request.message)

    # 6. Initialize async OpenAI client
    client = openai.AsyncOpenAI(
        api_key=settings.effective_api_key,
        base_url=settings.effective_base_url,
    )

    try:
        stream = await client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=messages,
            stream=True,
        )

        collected_text: List[str] = []
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    collected_text.append(delta)
                    # Vercel AI SDK text part: 0:"<text>"\n
                    yield f"0:{json.dumps(delta)}\n"

        assistant_text = "".join(collected_text)

        # 7. Persist turn to database in single transaction
        await persist_turn(db, thread.id, request.message, assistant_text)

        # 8. Yield Vercel AI SDK finish frame
        yield 'd:{"finishReason":"stop"}\n'

    except Exception as exc:
        logger.exception("Error streaming chat turn: %s", exc)
        # Vercel AI SDK error frame: 3:"<error>"\n
        yield f"3:{json.dumps(str(exc))}\n"
        raise
