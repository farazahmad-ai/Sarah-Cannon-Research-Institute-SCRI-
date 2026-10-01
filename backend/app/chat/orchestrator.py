"""Chat orchestrator executing streaming protocol queries with PydanticAI."""

from __future__ import annotations

import json
import logging
import re
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
from app.assistant.prompts import (
    build_no_evidence_refusal,
    format_protocol_context,
)
from app.assistant.schemas import ChatRequest, ProtocolPassage
from app.auth.jwt import AuthenticatedUser
from app.chat.guidance import (
    build_guidance_response,
    classify_guidance_intent,
)
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
from app.retrieval.hybrid import (
    DEFAULT_LIMIT,
    DEFAULT_MIN_SIMILARITY,
    retrieve_protocols,
)

logger = logging.getLogger(__name__)

# Maximum number of queries allowed in a single screening thread to prevent context decay
MAX_QUERIES_PER_SESSION: int = 3

# Maximum number of prior turns to include in the prompt.
# Set to 2 (1 previous Q&A pair) to provide pronoun context ("that same patient")
# while preventing multi-turn essay bloat that causes lost-in-the-middle hallucinations.
MAX_HISTORY_TURNS: int = 2

# Soft token ceiling for prior conversation history passed to the LLM.
# Calculated roughly as len(text) // 4. History is trimmed tail-first so the most
# recent turns are preserved (D-5).
MAX_HISTORY_TOKENS: int = 8_000

NCT_PATTERN = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)

DISEASE_KEYWORDS: dict[str, list[str]] = {
    "breast_cancer": [
        "breast cancer",
        "tnbc",
        "triple-negative",
        "her2-positive breast",
        "her2-low breast",
        "er+/her2-",
        "mbc",
    ],
    "colorectal_cancer": ["colorectal", "colon cancer", "rectal cancer", "mcrc", "crc"],
    "non_small_cell_lung_cancer": ["lung cancer", "nsclc", "non-small cell lung"],
    "melanoma": ["melanoma"],
    "lymphoma_car_t": ["lymphoma", "car-t", "cart", "dlbcl", "non-hodgkin"],
}


def _detect_single_disease_category(message: str) -> str | None:
    """Detect if the coordinator's question specifically and uniquely targets a single cancer category."""
    lowered = message.lower()
    matched = [
        cat for cat, kw_list in DISEASE_KEYWORDS.items() if any(kw in lowered for kw in kw_list)
    ]
    if len(matched) == 1:
        return matched[0]
    return None


def build_retrieval_query(message: str, history: list[ChatMessage]) -> str:
    """Anchor follow-up retrieval queries to active clinical trials.

    When a coordinator asks a follow-up question (e.g., 'What about prior steroid use
    for that same patient?'), naive retrieval loses trial context because the NCT ID
    was only cited in earlier turns.

    If the current query does NOT explicitly specify an NCT ID, this function prepends
    the active NCT ID(s) so hybrid retrieval (vector + FTS) searches within the same protocol.
    Note: It intentionally does NOT prepend prior section headers (e.g. chemotherapy headers)
    to prevent polluting queries about distinct criteria (e.g. surgery or radiation).
    """
    if not history or not message.strip():
        return message

    if NCT_PATTERN.search(message):
        return message

    target_ncts = extract_target_nct_ids(message, history)
    if not target_ncts:
        return message

    anchor_str = " ".join(target_ncts[:2])
    return f"{anchor_str} {message}"


def extract_target_nct_ids(message: str, history: list[ChatMessage]) -> list[str]:
    """Identify target clinical trial NCT IDs for the current turn.

    1. If the user's message explicitly mentions one or more NCT IDs, those take precedence.
    2. If the user's message does NOT mention an NCT ID, scan history backward for the
       most recent assistant turn with verified citations to inherit active trials.
    3. Fallback: scan recent message text backward for any mentioned NCT IDs.
    4. Return a deduplicated list of uppercase NCT IDs (e.g. ['NCT07659782']).
    """
    explicit = NCT_PATTERN.findall(message)
    if explicit:
        return list(dict.fromkeys(n.upper() for n in explicit))

    # Priority 1: Check verified citations from recent assistant messages
    for m in reversed(history):
        if (
            m.role == "assistant"
            and getattr(m, "citations", None)
            and not _is_refusal_or_unverified(m)
        ):
            anchors: list[str] = []
            for c in m.citations:
                nct = getattr(c, "nct_id", None) or (
                    c.get("nct_id") if isinstance(c, dict) else None
                )
                if nct and nct.upper() not in anchors:
                    anchors.append(nct.upper())
            if anchors:
                return anchors

    # Priority 2: Fallback to scanning message text backward
    for m in reversed(history):
        found = NCT_PATTERN.findall(m.content)
        if found:
            return list(dict.fromkeys(n.upper() for n in found))

    return []


def _is_refusal_or_unverified(msg: ChatMessage) -> bool:
    """Check if an assistant message was a refusal or unverified turn that should not poison LLM context."""
    if msg.role != "assistant":
        return False
    # If the message has verified protocol citations, it is grounded clinical context
    if msg.citations:
        return False
    meta = msg.metadata_json or {}
    if meta.get("intent") in ("greeting", "guidance", "catalog", "capabilities", "acknowledgment"):
        return True
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


def _is_screening_query(msg: ChatMessage) -> bool:
    """Check if a user message is an actual clinical screening query subject to session limits."""
    if msg.role != "user":
        return False
    meta = msg.metadata_json or {}
    return meta.get("intent") not in (
        "greeting",
        "guidance",
        "catalog",
        "capabilities",
        "acknowledgment",
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
                    request.message[:45] + "..." if len(request.message) > 45 else request.message
                )
                await pre_session.flush()
        else:
            initial_title = (
                request.message[:45] + "..." if len(request.message) > 45 else request.message
            )
            thread = await create_thread(pre_session, user_uuid, title=initial_title)
            thread_id = thread.id

        # 3. Load prior history (trimmed to safe context window)
        full_history = await list_messages(pre_session, thread_id, user_uuid)
        history = _trim_history(full_history)

        # 3a. Fast Guidance & Greeting Intent Router (0ms / 0 tokens / Quota-exempt)
        guidance_intent = classify_guidance_intent(request.message)
        if guidance_intent:
            logger.info(
                "Guidance intent detected for thread %s [intent=%s]: '%s'",
                thread_id,
                guidance_intent,
                request.message,
            )
            corpus_manifest = await get_corpus_manifest(pre_session)
            await pre_session.commit()

            guidance_msg = build_guidance_response(guidance_intent, corpus_manifest)
            yield f"0:{json.dumps(guidance_msg)}\n"
            yield 'd:{"finishReason":"stop"}\n'

            try:
                async with async_session_factory() as post_session:
                    await persist_turn(
                        post_session,
                        thread_id,
                        request.message,
                        guidance_msg,
                        citations=[],
                        user_metadata={"intent": guidance_intent},
                        assistant_metadata={"intent": "guidance", "grounded": True},
                    )
                    await post_session.commit()
            except BaseException as exc:
                logger.error(
                    "Failed to persist guidance turn for thread %s: %s",
                    thread_id,
                    exc,
                )
            return

        # 3b. Session query cap: prevent context decay, token bloat, and attention loss
        user_queries_count = sum(1 for m in full_history if _is_screening_query(m))
        if user_queries_count >= MAX_QUERIES_PER_SESSION:
            logger.info(
                "Session limit reached for thread %s (%d queries)",
                thread_id,
                user_queries_count,
            )
            session_limit_msg = (
                "**Screening Session Limit Reached (3/3 Queries)**\n\n"
                "To guarantee strict protocol grounding, prevent token degradation, and ensure patient safety, "
                "individual screening sessions are capped at 3 queries.\n\n"
                "Please click **'New Chat'** in the sidebar to start a fresh screening session for your next inquiry."
            )
            yield f"0:{json.dumps(session_limit_msg)}\n"
            yield 'd:{"finishReason":"stop"}\n'

            try:
                async with async_session_factory() as post_session:
                    await persist_turn(
                        post_session,
                        thread_id,
                        request.message,
                        session_limit_msg,
                        citations=[],
                    )
                    await post_session.commit()
            except BaseException as exc:
                logger.error(
                    "Failed to persist session limit turn for thread %s: %s", thread_id, exc
                )
            return

        # 4. Retrieve candidate protocol passages via targeted or partitioned hybrid retrieval
        target_ncts = extract_target_nct_ids(request.message, full_history)
        retrieval_query = build_retrieval_query(request.message, full_history)

        passages: list[ProtocolPassage] = []
        if len(target_ncts) == 1:
            # Single-trial isolation: strictly scope retrieval to the active trial
            # Prevents other trials from leaking unrelated criteria into the context
            single_nct = target_ncts[0]
            logger.info(
                "Single-trial isolated retrieval for thread %s [trial=%s]: '%s'",
                thread_id,
                single_nct,
                retrieval_query,
            )
            passages = await retrieve_protocols(
                pre_session,
                retrieval_query,
                nct_id=single_nct,
                limit=DEFAULT_LIMIT,
                min_similarity=DEFAULT_MIN_SIMILARITY,
            )
        elif len(target_ncts) > 1:
            # Multi-trial balanced retrieval: run partitioned sub-queries per trial
            # Prevents Trial A from crowding out Trial B in shared candidate pools
            quota_per_trial = max(4, DEFAULT_LIMIT // len(target_ncts))
            logger.info(
                "Multi-trial partitioned retrieval for thread %s [trials=%s, quota=%d]: '%s'",
                thread_id,
                target_ncts,
                quota_per_trial,
                request.message,
            )
            seen_chunk_ids: set[uuid.UUID] = set()
            for nct in target_ncts[:3]:  # Cap at top 3 active trials to preserve context budget
                trial_passages = await retrieve_protocols(
                    pre_session,
                    f"{nct} {request.message}",
                    nct_id=nct,
                    limit=quota_per_trial,
                    min_similarity=DEFAULT_MIN_SIMILARITY,
                )
                for p in trial_passages:
                    if p.chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(p.chunk_id)
                        passages.append(p)
        else:
            # Global corpus retrieval: broad disease or exploratory query
            # If the coordinator specifically asks about a single disease indication, scope retrieval strictly to that category
            matched_category = _detect_single_disease_category(request.message)
            if matched_category:
                logger.info(
                    "Disease-scoped retrieval for thread %s [category=%s]: '%s'",
                    thread_id,
                    matched_category,
                    request.message,
                )
            passages = await retrieve_protocols(
                pre_session,
                request.message,
                disease_category=matched_category,
                limit=DEFAULT_LIMIT,
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

    # Only inject corpus manifest if user is asking about overall catalog coverage
    is_coverage_query = any(
        k in request.message.lower()
        for k in (
            "what trials",
            "which trials",
            "list trials",
            "what diseases",
            "coverage",
            "how many trials",
        )
    )
    manifest_for_prompt = corpus_manifest if (is_coverage_query or not passages) else {}

    # 5. Build agent dependencies and message history
    deps = OncologyAgentDeps(
        user_id=user_uuid,
        thread_id=thread_id,
        retrieved_passages=passages,
        corpus_manifest=manifest_for_prompt,
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
        context_block = format_protocol_context(passages)
        prompt_with_instructions = (
            f"{context_block}\n\n"
            f"User Question: {request.message}\n\n"
            "[MANDATORY CITATION & CLINICAL SAFETY INSTRUCTIONS:\n"
            "1. Every single factual criterion, washout duration, or threshold must cite its exact supporting protocol passage using [NCT ID, Section Header] from the Protocol Context above.\n"
            "2. FORMAT CITATIONS WITH LITERAL BRACKETS: Citations must always be enclosed in literal square brackets, e.g. [NCT07340541, Study Design & Objectives]. Plain text citations without brackets will fail grounding verification.\n"
            "3. Report NUMERICAL TIMEFRAMES EXACTLY as written in the passage (e.g., '1 week', '4 weeks', '14 days'). NEVER average, combine, round, or extrapolate numbers between different criteria.\n"
            "4. STRICT DISEASE ISOLATION: If the question asks about a specific disease (e.g., breast cancer), ONLY use and cite passages from trials investigating that disease. NEVER borrow criteria from another cancer (e.g., NSCLC) or claim that concepts are similar. If the protocols for that disease do not state a criterion, declare protocol silence.\n"
            "5. If multiple criteria are asked about or retrieved (e.g., prior lines and refractory status), state each one separately under its own bullet point with its own individual citation matching the exact passage header.]"
        )

        async with oncology_agent.run_stream(
            prompt_with_instructions,
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
