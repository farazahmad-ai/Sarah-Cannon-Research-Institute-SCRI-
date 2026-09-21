"""Unit tests for chat streaming orchestrator, context window boundaries, and C1 sanitization.

Covers Finding M3 & C1:
- Verifies _trim_history respects the 10-turn cap and soft token ceiling.
- Verifies tail preservation so the most recent turns are retained.
- Verifies that GroundingValidator.sanitize_unverified_citations replaces fabricated brackets.
"""

import uuid

from app.assistant.schemas import ProtocolPassage
from app.chat.orchestrator import MAX_HISTORY_TURNS, _trim_history
from app.database.models import ChatMessage
from app.grounding.validator import GroundingValidator


def _make_msg(role: str, content: str) -> ChatMessage:
    return ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role=role,
        content=content,
    )


def test_trim_history_empty():
    """Empty history returns empty list."""
    assert _trim_history([]) == []


def test_trim_history_caps_at_max_turns():
    """History longer than MAX_HISTORY_TURNS is capped to the most recent turns."""
    messages = [_make_msg("user", f"Turn {i}") for i in range(25)]
    trimmed = _trim_history(messages, max_turns=MAX_HISTORY_TURNS)

    assert len(trimmed) == MAX_HISTORY_TURNS
    # Tail preservation: the last message must match the last message in input
    assert trimmed[-1].content == "Turn 24"
    assert trimmed[0].content == "Turn 15"


def test_trim_history_token_budget_preserves_tail():
    """When turns exceed token budget, older turns are trimmed while recent turns are kept."""
    short_msg = _make_msg("user", "Short question")
    long_msg = _make_msg("assistant", "Very long response " * 2000)  # ~6,000 tokens
    recent_msg = _make_msg("user", "Recent follow-up question")

    messages = [long_msg, short_msg, recent_msg]
    # Restrict budget so long_msg cannot fit alongside recent_msg
    trimmed = _trim_history(messages, max_turns=10, max_tokens=1000)

    # Must preserve the most recent message
    assert recent_msg in trimmed
    assert long_msg not in trimmed


def test_orchestrator_c1_sanitization_replaces_hallucinated_citations():
    """C1 Grounding Guardrail: Unretrieved NCT IDs are replaced with unverified reference tags."""
    retrieved_passages = [
        ProtocolPassage(
            chunk_id=uuid.uuid4(),
            nct_id="NCT05794958",
            section_type="ELIGIBILITY_INCLUSION",
            section_header="Eligibility: Inclusion Criterion #2",
            chunk_text="Age 18 years or older with histologically confirmed NSCLC.",
            similarity=0.82,
        )
    ]

    # Model generates one real citation and one fabricated citation
    model_output = (
        "Eligible patients must be adults [NCT05794958, Inclusion Criterion #2]. "
        "Also prior immunotherapy is allowed [NCT09999999, Exclusion #5]."
    )

    sanitized = GroundingValidator.sanitize_unverified_citations(
        model_output,
        retrieved_passages,
    )

    # Real citation is kept intact
    assert "[NCT05794958, Inclusion Criterion #2]" in sanitized
    # Fabricated citation is sanitized with warning label
    assert "[NCT09999999 (Unverified Protocol Reference)]" in sanitized
    assert "[NCT09999999, Exclusion #5]" not in sanitized

    # Only the verified citation is parsed and returned
    verified = GroundingValidator.validate_citations(sanitized, retrieved_passages)
    assert len(verified) == 1
    assert verified[0].nct_id == "NCT05794958"
