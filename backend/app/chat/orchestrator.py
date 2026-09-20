"""Streaming chat orchestrator for SCRI Oncology Copilot.

Orchestrates the chat turn pipeline:
1. Bootstraps user profile in database.
2. Resolves or creates the chat thread.
3. Retrieves relevant protocol passages (stubbed in this slice).
4. Assembles prompt with system instructions, conversation history, and protocol context.
5. Streams completions from OpenAI in Vercel AI SDK data-stream format.
6. Persists the completed turn to the database — in its own short-lived session,
   guarded by BaseException so a late client disconnect still saves the answer.

Session ownership (D-3 / D-4):
  The route layer passes NO session to this function. The orchestrator opens and
  closes its own short-lived sessions at each DB boundary so that zero pooled
  connections are held while tokens are streaming (which can take 5–30 seconds).
  Two sessions are used per turn:
    - pre_session:  profile upsert + thread resolve + history fetch → commit → close
    - post_session: persist_turn → commit → close  (guarded by BaseException)
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
from app.database.session import async_session_factory

logger = logging.getLogger(__name__)

# Maximum number of prior turns to include in the prompt.
# Bounded here rather than in the DB query so the DB always returns the full
# history (useful for future analytics) while the LLM only sees a safe window.
_MAX_HISTORY_MESSAGES = 10

# Approximate token budget for conversation history.
# Uses the same word_count * 1.3 heuristic as the chunker — no tiktoken dep.
# If history exceeds this, we slice from the tail (most recent turns).
_MAX_HISTORY_TOKENS = 8_000

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


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: word_count × 1.3 (GPT tokenizer average)."""
    return int(len(text.split()) * 1.3)


def _trim_history(history: List[ChatMessage]) -> List[ChatMessage]:
    """Return the most-recent tail of history that fits within token and count budgets.

    We enforce both a message count cap (_MAX_HISTORY_MESSAGES) and a soft token
    budget (_MAX_HISTORY_TOKENS) because a single long assistant response can blow
    the context window even with few messages. We take the tail (most recent) so
    that the conversation stays coherent.
    """
    # Apply message count cap first
    capped = history[-_MAX_HISTORY_MESSAGES:]

    # Then trim further if total token estimate exceeds budget
    total = 0
    cutoff = len(capped)
    for i in range(len(capped) - 1, -1, -1):
        total += _estimate_tokens(capped[i].content)
        if total > _MAX_HISTORY_TOKENS:
            cutoff = i + 1
            break
    return capped[cutoff:]


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
    prior = [{"role": m.role, "content": m.content} for m in _trim_history(history)]
    context_block = (
        f"[{passage.nct_id}, {passage.section_header}]\n{passage.chunk_text}"
    )
    user = {
        "role": "user",
        "content": f"Protocol Context:\n{context_block}\n\nQuestion: {user_message}",
    }
    return [system, *prior, user]


async def stream_chat_turn(
    user: AuthenticatedUser,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Execute streaming chat turn and yield Vercel AI SDK formatted frames.

    DB session strategy (D-3 / D-4):
      - pre_session: resolve thread + fetch history → committed before yielding
      - No session is held during token streaming
      - post_session: persist completed turn → committed after streaming
    """
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id

    # ------------------------------------------------------------------
    # Pre-stream block: all DB reads in one short-lived committed session.
    # The session is fully closed before we yield a single token, so no
    # connection is held while the LLM streams (D-4).
    # ------------------------------------------------------------------
    thread_id: uuid.UUID
    history: List[ChatMessage]

    async with async_session_factory() as pre_session:
        # 1. Guarantee profile exists
        await upsert_profile(pre_session, user_uuid, user.email)

        # 2. Get or create thread
        if request.thread_id is None:
            title = request.message.strip()[:60] or "New Screening Session"
            thread = await create_thread(pre_session, user_uuid, title=title)
        else:
            thread = await get_thread(pre_session, request.thread_id, user_uuid)

        thread_id = thread.id

        # 3. Fetch conversation history (ownership already verified above)
        history = await list_messages(pre_session, thread_id, user_uuid)

        await pre_session.commit()
    # pre_session is now fully closed — connection returned to pool

    # 4. Retrieve protocol passage (stub — replaced by hybrid.retrieve() in Phase 4)
    passage = _stub_retrieve(request.message)

    # 5. Build prompt messages
    messages = build_openai_messages(history, passage, request.message)

    # 6. Initialize async OpenAI client
    client = openai.AsyncOpenAI(
        api_key=settings.effective_api_key,
        base_url=settings.effective_base_url,
    )

    # ------------------------------------------------------------------
    # Stream block: no DB session is open during token delivery.
    # ------------------------------------------------------------------
    stream_error: Exception | None = None
    collected_text: List[str] = []

    try:
        stream = await client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    collected_text.append(delta)
                    # Vercel AI SDK text part: 0:"<text>"\n
                    yield f"0:{json.dumps(delta)}\n"

    except Exception as exc:
        logger.exception("Error streaming chat turn: %s", exc)
        stream_error = exc
        yield f"3:{json.dumps(str(exc))}\n"

    if not stream_error:
        # Vercel AI SDK finish frame
        yield 'd:{"finishReason":"stop"}\n'

    # ------------------------------------------------------------------
    # Post-stream block: persist in a fresh short-lived session.
    # Guarded by BaseException so a late client disconnect (CancelledError)
    # still saves the completed answer rather than silently losing it (D-3).
    # Persists even on stream_error (R-6) so the coordinator's question is
    # not lost on reload.
    # ------------------------------------------------------------------
    assistant_text = "".join(collected_text)
    if stream_error and not assistant_text:
        assistant_text = f"[Response interrupted: {stream_error}]"

    try:
        async with async_session_factory() as post_session:
            await persist_turn(post_session, thread_id, request.message, assistant_text)
            await post_session.commit()
    except BaseException as exc:
        logger.error(
            "Failed to persist chat turn for thread %s: %s",
            thread_id,
            exc,
        )
        # Do not re-raise — log and move on.
