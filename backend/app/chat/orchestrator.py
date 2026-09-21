"""Chat orchestrator executing streaming protocol queries with PydanticAI."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.assistant.agent import oncology_agent
from app.assistant.deps import OncologyAgentDeps
from app.assistant.prompts import build_no_evidence_refusal
from app.assistant.schemas import ChatRequest, ProtocolPassage
from app.auth.jwt import AuthenticatedUser
from app.database.chats import (
    create_thread,
    get_thread,
    list_messages,
    persist_turn,
    upsert_profile,
)
from app.database.models import ChatMessage
from app.database.session import async_session_factory
from app.database.trials import get_corpus_manifest
from app.grounding.validator import GroundingValidator
from app.retrieval.hybrid import DEFAULT_MIN_SIMILARITY, retrieve_protocols

logger = logging.getLogger(__name__)

# Maximum number of prior turns to include in the prompt.
# Bounded here rather than in the DB query so the DB always returns the full
# history (useful for future analytics) while the LLM only sees a safe window.
MAX_HISTORY_TURNS: int = 10

# Soft token ceiling for prior conversation history passed to the LLM.
# Calculated roughly as len(text) // 4. History is trimmed tail-first so the most
# recent turns are preserved (D-5).
MAX_HISTORY_TOKENS: int = 8_000


def _is_refusal_or_unverified(msg: ChatMessage) -> bool:
    """Check if an assistant message was a refusal or unverified turn that should not poison LLM context."""
    if msg.role != "assistant":
        return False
    # If the message has verified protocol citations, it is grounded clinical context
    if msg.citations:
        return False
    lowered = msg.content.lower()
    return any(
        marker in lowered
        for marker in (
            "cannot answer",
            "not contain protocol information",
            "does not contain protocol information",
            "unable to provide",
            "don't have access",
            "do not have access",
            "no protocol passage could be verified",
            "evidence notice",
        )
    )


def _trim_history(
    messages: list[ChatMessage],
    max_turns: int = MAX_HISTORY_TURNS,
    max_tokens: int = MAX_HISTORY_TOKENS,
) -> list[ChatMessage]:
    """Trim conversation history to the most recent turns within a token budget."""
    if not messages:
        return []

    # Step 1: Cap at the last N messages
    recent = messages[-max_turns:]

    # Step 2: Trim tail-first until under the token ceiling
    selected: list[ChatMessage] = []
    running_tokens = 0

    for msg in reversed(recent):
        msg_tokens = len(msg.content) // 4
        if running_tokens + msg_tokens > max_tokens and selected:
            logger.info(
                "History trimmed at %d tokens (%d messages preserved)",
                running_tokens,
                len(selected),
            )
            break
        selected.insert(0, msg)
        running_tokens += msg_tokens

    return selected


async def stream_chat_turn(
    user: AuthenticatedUser,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Execute a complete streaming chat turn.

    Lifecycle:
    1. pre_session:
       - Upsert coordinator profile
       - Resolve or create thread
       - Load prior conversation history
       - Run hybrid retrieval across landmark trial protocols
       - Commit and CLOSE the session
    2. Stream tokens from oncology_agent using Vercel AI SDK data-stream protocol.
    3. C1: Sanitize ungrounded citations; emit update frame if corrected.
    4. post_session (guarded by BaseException):
       - Extract verified citations
       - Persist both messages to the database
       - Commit and CLOSE the session
    """
    user_uuid = uuid.UUID(user.id) if isinstance(user.id, str) else user.id

    # ------------------------------------------------------------------
    # Pre-stream block: short-lived DB session for metadata and retrieval.
    # ------------------------------------------------------------------
    async with async_session_factory() as pre_session:
        # 1. Upsert profile so coordinator row exists in this DB
        await upsert_profile(pre_session, user_uuid, user.email)

        # 2. Resolve or create thread
        if request.thread_id:
            thread = await get_thread(pre_session, request.thread_id, user_uuid)
            thread_id = thread.id
            if thread.title in ("New Screening Session", "New session", ""):
                thread.title = (
                    request.message[:45] + "..."
                    if len(request.message) > 45
                    else request.message
                )
                await pre_session.flush()
        else:
            initial_title = (
                request.message[:45] + "..."
                if len(request.message) > 45
                else request.message
            )
            thread = await create_thread(pre_session, user_uuid, title=initial_title)
            thread_id = thread.id

        # 3. Load prior history (trimmed to safe context window)
        full_history = await list_messages(pre_session, thread_id, user_uuid)
        history = _trim_history(full_history)

        # 4. Retrieve candidate protocol passages via hybrid retrieval
        passages: list[ProtocolPassage] = await retrieve_protocols(
            pre_session,
            request.message,
            min_similarity=DEFAULT_MIN_SIMILARITY,
        )

        # 5. Corpus manifest so coverage questions are answerable and refusals
        #    can name the actual disease areas in the system (C3 / N3).
        corpus_manifest = await get_corpus_manifest(pre_session)

        await pre_session.commit()
    # pre_session is now fully closed — connection returned to pool

    # ------------------------------------------------------------------
    # C3 / N1: Minimum-evidence gate.
    #
    # If retrieval returned zero relevant passages, DO NOT call the LLM at all.
    # An LLM prompted with empty context is precisely the condition under which
    # it answers from general medical knowledge (the pediatric GBM hallucination
    # case). The refusal below is deterministic: no tokens, no drift, auditable.
    # ------------------------------------------------------------------
    if not passages:
        logger.info(
            "No-evidence refusal for thread %s (query had no matching passages)",
            thread_id,
        )
        refusal_text = build_no_evidence_refusal(request.message, corpus_manifest)

        # Deliver as a normal stream so the client needs no special handling.
        yield f"0:{json.dumps(refusal_text)}\n"
        yield 'd:{"finishReason":"stop"}\n'

        try:
            async with async_session_factory() as post_session:
                await persist_turn(
                    post_session,
                    thread_id,
                    request.message,
                    refusal_text,
                    citations=[],
                )
                await post_session.commit()
        except BaseException as exc:
            logger.error(
                "Failed to persist no-evidence refusal for thread %s: %s",
                thread_id,
                exc,
            )
        return

    # 5. Build agent dependencies and message history
    deps = OncologyAgentDeps(
        user_id=user_uuid,
        thread_id=thread_id,
        retrieved_passages=passages,
        corpus_manifest=corpus_manifest,
    )

    model_history: list[ModelMessage] = []
    # Build conversational history in (user, assistant) pairs.
    # Exclude prior turns where the assistant gave unverified answers or negative refusals.
    # Passing refusal turns causes few-shot prompt poisoning, where the LLM adopts a refusal
    # persona ("I don't have access to databases") and ignores valid retrieved protocol passages.
    i = 0
    while i < len(history):
        m = history[i]
        if m.role == "user":
            if i + 1 < len(history) and history[i + 1].role == "assistant":
                asst = history[i + 1]
                if not _is_refusal_or_unverified(asst):
                    content = asst.content
                    if "> ⚠️ **Evidence notice:**" in content:
                        parts = content.split("\n\n", 1)
                        if len(parts) > 1:
                            content = parts[1]
                    model_history.append(ModelRequest(parts=[UserPromptPart(content=m.content)]))
                    model_history.append(ModelResponse(parts=[TextPart(content=content)]))
                i += 2
                continue
            else:
                model_history.append(ModelRequest(parts=[UserPromptPart(content=m.content)]))
                i += 1
                continue
        elif m.role == "assistant":
            if not _is_refusal_or_unverified(m):
                content = m.content
                if "> ⚠️ **Evidence notice:**" in content:
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1:
                        content = parts[1]
                model_history.append(ModelResponse(parts=[TextPart(content=content)]))
            i += 1
        else:
            i += 1

    # ------------------------------------------------------------------
    # Stream block: no DB session is open during token delivery.
    # ------------------------------------------------------------------
    stream_error: Exception | None = None
    collected_text: list[str] = []

    try:
        async with oncology_agent.run_stream(
            request.message,
            deps=deps,
            message_history=model_history,
        ) as result:
            async for delta in result.stream_text(delta=True):
                if delta:
                    collected_text.append(delta)
                    # Vercel AI SDK text part: 0:"<text>"\n
                    yield f"0:{json.dumps(delta)}\n"

    except Exception as exc:
        logger.exception("Error streaming chat turn: %s", exc)
        stream_error = exc
        yield f"3:{json.dumps(str(exc))}\n"

    assistant_text = "".join(collected_text)
    if stream_error and not assistant_text:
        assistant_text = f"[Response interrupted: {stream_error}]"

    # ------------------------------------------------------------------
    # C1: Sanitize unverified/hallucinated citations before delivery finish
    # ------------------------------------------------------------------
    sanitized_text = GroundingValidator.sanitize_unverified_citations(
        assistant_text,
        passages,
    )

    if sanitized_text != assistant_text:
        logger.warning(
            "Sanitized unverified citations in turn for thread %s",
            thread_id,
        )
        # Emit replacement frame so the client replaces raw tokens with sanitized text
        yield f"u:{json.dumps(sanitized_text)}\n"
        assistant_text = sanitized_text

    if not stream_error:
        # Vercel AI SDK finish frame
        yield 'd:{"finishReason":"stop"}\n'

    # ------------------------------------------------------------------
    # Post-stream block: persist in a fresh short-lived session.
    # Guarded by BaseException so a late client disconnect (CancelledError)
    # still saves the completed answer rather than silently losing it (D-3).
    # ------------------------------------------------------------------
    try:
        # Validate and extract grounded citations against the retrieved passages
        verified_citations = GroundingValidator.validate_citations(
            assistant_text,
            passages,
        )

        # ------------------------------------------------------------------
        # C3 / N1b: evidence-coverage warning.
        #
        # Passages were retrieved but the answer cites none of them. A genuine
        # negative refusal ("The protocol does not state [X]") legitimately has
        # no citations and is exempted; anything else that is long enough to
        # contain factual claims but carries zero citations is unverified and
        # must be visibly flagged rather than presented as grounded.
        # ------------------------------------------------------------------
        if not verified_citations and passages:
            lowered = assistant_text.lower()
            is_legitimate_refusal = any(
                marker in lowered
                for marker in (
                    "does not state",
                    "does not contain",
                    "does not specify",
                    "does not include",
                    "not contain protocol information",
                    "cannot answer",
                    "unable to provide",
                    "not available in this system",
                    "do not address",
                    "no protocol passages",
                )
            )
            if not is_legitimate_refusal and len(assistant_text) > 200:
                notice = (
                    "> ⚠️ **Evidence notice:** no protocol passage could be verified as the "
                    "source of this answer. Treat the statements below as unverified and "
                    "confirm directly in the protocol documents.\n\n"
                )
                assistant_text = notice + assistant_text
                logger.warning(
                    "Uncited answer flagged for thread %s (passages retrieved, zero verified citations)",
                    thread_id,
                )
                yield f"u:{json.dumps(assistant_text)}\n"

        async with async_session_factory() as post_session:
            await persist_turn(
                post_session,
                thread_id,
                request.message,
                assistant_text,
                citations=verified_citations,
            )
            await post_session.commit()
    except BaseException as exc:
        logger.error(
            "Failed to persist chat turn for thread %s: %s",
            thread_id,
            exc,
        )
        # Do not re-raise — log and move on.
