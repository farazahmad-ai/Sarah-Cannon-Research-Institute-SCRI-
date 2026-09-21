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

import json
import logging
import uuid
from collections.abc import AsyncGenerator

import openai

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
from app.retrieval.hybrid import DEFAULT_MIN_SIMILARITY, retrieve_protocols

logger = logging.getLogger(__name__)

# Maximum number of prior turns to include in the prompt.
# Bounded here rather than in the DB query so the DB always returns the full
# history (useful for future analytics) while the LLM only sees a safe window.
_MAX_HISTORY_MESSAGES = 10

# Soft token ceiling for conversation history (~8 000 tokens ≈ 6 000 words)
_MAX_HISTORY_TOKENS = 8000

SYSTEM_PROMPT = (
    "You are an expert oncology clinical trial assistant for Sarah Cannon Research Institute (SCRI). "
    "Your mission is to provide accurate, grounded answers to clinical research coordinators "
    "and investigators evaluating patient eligibility for cancer clinical trials.\n\n"
    "CRITICAL RULES:\n"
    "1. ABSOLUTE GROUNDING: Every factual claim must cite a specific protocol section using bracket notation: "
    "[NCT ID, Section Header] (e.g. [NCT07659782, Eligibility: Exclusion Criterion #4]).\n"
    "2. ZERO HALLUCINATION: Never fabricate eligibility criteria, lab thresholds, or washout periods. "
    "If the provided protocol context does not contain the answer, explicitly state: 'The protocol does not state [X].' "
    "Never guess, extrapolate, or generalize from other medical literature."
)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: word_count × 1.3 (GPT tokenizer average)."""
    return int(len(text.split()) * 1.3)


def _trim_history(history: list[ChatMessage]) -> list[ChatMessage]:
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
    history: list[ChatMessage],
    passages: list[ProtocolPassage],
    user_message: str,
) -> list[dict[str, str]]:
    """Assemble the OpenAI messages array for chat completion with grounded passages."""
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT,
    }
    prior = [{"role": m.role, "content": m.content} for m in _trim_history(history)]

    if passages:
        formatted_passages = []
        for idx, p in enumerate(passages, start=1):
            formatted_passages.append(
                f"[Passage {idx} | {p.nct_id}, {p.section_header}]\n{p.chunk_text}"
            )
        context_block = "\n\n".join(formatted_passages)
        user_content = f"Protocol Context:\n{context_block}\n\nQuestion: {user_message}"
    else:
        user_content = (
            "Protocol Context: No matching protocol passages retrieved for this query.\n\n"
            f"Question: {user_message}"
        )

    user = {
        "role": "user",
        "content": user_content,
    }
    return [system, *prior, user]


async def stream_chat_turn(
    user: AuthenticatedUser,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Execute streaming chat turn and yield Vercel AI SDK formatted frames.

    DB session strategy (D-3 / D-4):
      - pre_session: resolve thread + fetch history + hybrid retrieval → committed before yielding
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
    history: list[ChatMessage]
    passages: list[ProtocolPassage]

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

        # 4. Execute hybrid retrieval inside pre_session before commit/close
        passages = await retrieve_protocols(
            pre_session,
            request.message,
            min_similarity=DEFAULT_MIN_SIMILARITY,
        )

        await pre_session.commit()
    # pre_session is now fully closed — connection returned to pool

    # 5. Build prompt messages with grounded passages
    messages = build_openai_messages(history, passages, request.message)

    # 6. Initialize async OpenAI client
    client = openai.AsyncOpenAI(
        api_key=settings.effective_api_key,
        base_url=settings.effective_base_url,
    )

    # ------------------------------------------------------------------
    # Stream block: no DB session is open during token delivery.
    # ------------------------------------------------------------------
    stream_error: Exception | None = None
    collected_text: list[str] = []

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
