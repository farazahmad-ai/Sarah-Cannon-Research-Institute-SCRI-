"""Unit tests for multi-turn query augmentation and context retention in SCRI Oncology Copilot.

Covers Roadmap Phase 8.1:
- Verifies build_retrieval_query preserves standalone queries with explicit NCT IDs.
- Verifies build_retrieval_query anchors follow-up questions to the active trial's citations.
- Verifies deduplication of NCT IDs and section headers in the anchor prefix.
- Verifies that negative refusals and unverified turns do not pollute follow-up queries.
"""

from __future__ import annotations

import uuid

from app.chat.orchestrator import build_retrieval_query, extract_target_nct_ids
from app.database.models import ChatMessage, MessageCitation


def _make_msg(
    role: str,
    content: str,
    citations: list[MessageCitation] | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role=role,
        content=content,
    )
    if citations is not None:
        msg.citations = citations
    return msg


def _make_citation(nct_id: str, section_header: str) -> MessageCitation:
    return MessageCitation(
        id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        nct_id=nct_id,
        section_header=section_header,
        verbatim_quote="Sample verbatim protocol quote",
        citation_index=0,
    )


def test_build_retrieval_query_empty_history():
    """First turn with no prior history returns the raw user query unchanged."""
    query = "Does NCT05794958 allow patients with treated brain metastases?"
    augmented = build_retrieval_query(query, [])
    assert augmented == query


def test_build_retrieval_query_explicit_nct_in_user_message():
    """If user explicitly queries an NCT ID, do not prepend context from prior trials."""
    history = [
        _make_msg("user", "Tell me about NCT05794958 brain met criteria."),
        _make_msg(
            "assistant",
            "NCT05794958 requires stable brain metastases [NCT05794958, Exclusion #7].",
            citations=[_make_citation("NCT05794958", "Eligibility: Exclusion Criterion #7")],
        ),
    ]

    # User switches to a different trial explicitly
    query = "What about NCT06529523 for brain metastases?"
    augmented = build_retrieval_query(query, history)
    # Must remain exact query, without prepending NCT05794958
    assert augmented == query
    assert "NCT05794958" not in augmented


def test_build_retrieval_query_anchors_to_previous_citations():
    """Follow-up questions lacking an NCT ID inherit the active trial's anchor context."""
    history = [
        _make_msg("user", "What are the eligibility criteria for NCT05794958 regarding brain mets?"),
        _make_msg(
            "assistant",
            "NCT05794958 allows stable brain metastases [NCT05794958, Eligibility: Exclusion Criterion #7].",
            citations=[_make_citation("NCT05794958", "Eligibility: Exclusion Criterion #7")],
        ),
    ]

    follow_up = "What about prior steroid use for that same patient?"
    augmented = build_retrieval_query(follow_up, history)

    # Must contain the active NCT ID followed by the follow-up question
    assert augmented.startswith("NCT05794958")
    assert follow_up in augmented


def test_build_retrieval_query_deduplicates_nct():
    """Multiple citations to the same trial are deduplicated in the anchor prefix."""
    history = [
        _make_msg("user", "Check NCT07659782 criteria."),
        _make_msg(
            "assistant",
            "Here are criteria [NCT07659782, Exclusion #1] and [NCT07659782, Exclusion #2].",
            citations=[
                _make_citation("NCT07659782", "Eligibility: Exclusion Criteria"),
                _make_citation("NCT07659782", "Eligibility: Exclusion Criteria"),
            ],
        ),
    ]

    follow_up = "Are patients with prior chemotherapy eligible?"
    augmented = build_retrieval_query(follow_up, history)

    # NCT07659782 should appear exactly once in the anchor prefix
    assert augmented.startswith("NCT07659782 ")
    assert augmented.count("NCT07659782") == 1


def test_build_retrieval_query_ignores_refusal_turns():
    """If the prior assistant turn was a negative refusal, do not anchor to it."""
    history = [
        _make_msg("user", "Can you check pediatric glioblastoma trials?"),
        _make_msg(
            "assistant",
            "The system cannot answer questions about pediatric glioblastoma because it is not in the corpus.",
            citations=[],
        ),
    ]

    next_query = "What trials are available for KRAS G12D in NSCLC?"
    augmented = build_retrieval_query(next_query, history)
    assert augmented == next_query


def test_build_retrieval_query_fallback_to_earlier_grounded_turn():
    """If the immediate last turn had no citations, search back to the most recent grounded turn."""
    history = [
        _make_msg("user", "Tell me about NCT05794958."),
        _make_msg(
            "assistant",
            "Found trial details [NCT05794958, Summary].",
            citations=[_make_citation("NCT05794958", "Brief Summary")],
        ),
        _make_msg("user", "Is there anything else?"),
        _make_msg(
            "assistant",
            "The protocol does not state additional biomarker criteria.",
            citations=[],  # Legitimate silence refusal without citations
        ),
    ]

    follow_up = "What about washout periods?"
    augmented = build_retrieval_query(follow_up, history)

    # Should anchor to NCT05794958 from the earlier grounded turn
    assert "NCT05794958" in augmented
    assert follow_up in augmented


def test_extract_target_nct_ids_from_message():
    """Explicit NCT IDs in the message take absolute precedence."""
    query = "What are the eligibility criteria for NCT07659782?"
    targets = extract_target_nct_ids(query, [])
    assert targets == ["NCT07659782"]


def test_extract_target_nct_ids_multiple_in_message():
    """Comparative queries naming 2 or more trials return all unique targets in order."""
    query = "Compare NCT07659782 and NCT06312137 regarding surgery washout."
    targets = extract_target_nct_ids(query, [])
    assert targets == ["NCT07659782", "NCT06312137"]


def test_extract_target_nct_ids_inherited_from_history():
    """Follow-up questions lacking an NCT ID inherit the active trial(s) from history citations."""
    history = [
        _make_msg("user", "Tell me about NCT07659782."),
        _make_msg(
            "assistant",
            "Found details [NCT07659782, Summary].",
            citations=[_make_citation("NCT07659782", "Summary")],
        ),
    ]

    follow_up = "What about surgery or radiation washout for that same patient?"
    targets = extract_target_nct_ids(follow_up, history)
    assert targets == ["NCT07659782"]


def test_extract_target_nct_ids_empty_for_general_query():
    """Broad queries without NCT IDs or prior citations return an empty target list."""
    query = "What trials are available for KRAS G12D in NSCLC?"
    targets = extract_target_nct_ids(query, [])
    assert targets == []

