"""Unit tests for the Conversational Guidance & Greeting Intent Router.

Verifies:
1. Fast classification of greetings ("hi", "hello", "good morning").
2. Fast classification of acknowledgments ("ok", "got it", "thanks").
3. Fast classification of capability inquiries ("what can you answer?", "what can you do", "help").
4. Fast classification of catalog overview inquiries ("what trials are loaded", "list trials").
5. Strict clinical safety: Queries mentioning NCT IDs or clinical terms (e.g. brain metastases, washout, ANC)
   are NEVER classified as guidance and must proceed to protocol retrieval.
6. Absence of informal emojis across all guidance templates.
7. Quota exemption: Guidance turns are not counted as clinical screening queries.
8. History isolation: Guidance responses are filtered out from LLM multi-turn prompts.
"""

import re
import uuid

import pytest

from app.chat.guidance import (
    build_guidance_response,
    classify_guidance_intent,
    is_guidance_intent,
)
from app.chat.orchestrator import _is_refusal_or_unverified, _is_screening_query
from app.database.models import ChatMessage


@pytest.mark.parametrize(
    "query",
    [
        "hi",
        "Hi!",
        "hello",
        "Hello!",
        "hello copilot",
        "hey there",
        "good morning",
        "Good afternoon",
        "howdy",
        "greetings",
    ],
)
def test_classify_greetings(query: str):
    """Greetings are recognized accurately."""
    assert classify_guidance_intent(query) == "greeting"
    assert is_guidance_intent(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "ok",
        "Ok",
        "okay",
        "OKAY",
        "alright",
        "all right",
        "got it",
        "understood",
        "cool",
        "sure",
        "fine",
        "sounds good",
        "perfect",
        "noted",
        "thanks",
        "thank you",
        "thx",
        "thank you so much",
    ],
)
def test_classify_acknowledgments(query: str):
    """Conversational acknowledgments are recognized accurately."""
    assert classify_guidance_intent(query) == "acknowledgment"
    assert is_guidance_intent(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "what can you do",
        "what can you do?",
        "what can you tell me",
        "what can you tell me ?",
        "then what can you answer?",
        "what can you answer?",
        "what can you answer then",
        "what else can you answer?",
        "what can i ask",
        "what can i ask you?",
        "what questions can i ask?",
        "what kind of questions can i ask",
        "how can you help",
        "how can you help me?",
        "how does this work",
        "who are you",
        "what is scri copilot",
        "help",
        "help me",
        "guide me",
        "instructions",
    ],
)
def test_classify_capabilities(query: str):
    """Capability and orientation questions are recognized accurately."""
    assert classify_guidance_intent(query) == "capabilities"
    assert is_guidance_intent(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "what trials do you have",
        "what trials do you have?",
        "what trials are loaded",
        "which trials are available",
        "what diseases do you cover",
        "list trials",
        "show active trials",
        "how many trials are loaded",
    ],
)
def test_classify_catalog_inquiries(query: str):
    """Corpus catalog inquiries are recognized accurately."""
    assert classify_guidance_intent(query) == "catalog"
    assert is_guidance_intent(query) is True


@pytest.mark.parametrize(
    "query",
    [
        # Explicit NCT ID
        "Does NCT05794958 allow brain metastases?",
        "Tell me about NCT06312137",
        "What are the inclusion criteria for NCT07659782?",
        # Specific clinical entities
        "What is the washout interval for checkpoint inhibitors?",
        "Which trials allow patients with pre-treated asymptomatic brain metastases?",
        "ANC count threshold below 1,000/µL",
        "Prior chemotherapy lines for metastatic breast cancer",
        "Does the lung protocol require EGFR mutation testing?",
        "What are the organ function limits for colorectal cancer?",
    ],
)
def test_clinical_queries_bypass_guidance(query: str):
    """Clinical questions are strictly NOT classified as guidance to preserve protocol grounding."""
    assert classify_guidance_intent(query) is None
    assert is_guidance_intent(query) is False


def test_build_guidance_response_content():
    """Guidance response includes manifest counts, capabilities, and exemplary queries without emojis."""
    manifest = {
        "breast_cancer": 5,
        "lung_cancer": 5,
        "colorectal_cancer": 5,
    }
    response = build_guidance_response("greeting", manifest)

    assert "SCRI Oncology Protocol Copilot" in response
    assert "Breast Cancer" in response
    assert "Lung Cancer" in response
    assert "Colorectal Cancer" in response
    assert "Exemplary Screening Queries" in response
    assert "checkpoint inhibitor" in response
    assert "brain metastases" in response
    assert "do not count against your 3-query clinical screening quota" in response

    # Rigorous check: strictly zero unicode emoji symbols
    assert not re.search(r"[\U00010000-\U0010ffff]", response), (
        "Emojis must not be present in guidance response"
    )


def test_build_acknowledgment_response():
    """Acknowledgment returns a professional clinical waiting prompt."""
    response = build_guidance_response("acknowledgment", {})
    assert "Understood" in response
    assert "eligibility criteria" in response
    assert not re.search(r"[\U00010000-\U0010ffff]", response)


def test_screening_query_cap_exemption():
    """Guidance and acknowledgment messages do not count towards the 3-query clinical screening session limit."""
    guidance_user_msg = ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role="user",
        content="hello",
        metadata_json={"intent": "greeting"},
    )
    ack_user_msg = ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role="user",
        content="ok",
        metadata_json={"intent": "acknowledgment"},
    )
    clinical_user_msg = ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role="user",
        content="Does NCT05794958 allow brain metastases?",
        metadata_json=None,
    )
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role="assistant",
        content="Guidance text",
    )

    assert _is_screening_query(guidance_user_msg) is False
    assert _is_screening_query(ack_user_msg) is False
    assert _is_screening_query(clinical_user_msg) is True
    assert _is_screening_query(assistant_msg) is False


def test_history_isolation_for_guidance_responses():
    """Guidance responses are filtered out from LLM multi-turn prompts to prevent context pollution."""
    guidance_asst_msg = ChatMessage(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role="assistant",
        content="### Welcome to SCRI Oncology Protocol Copilot...",
        metadata_json={"intent": "guidance"},
    )
    assert _is_refusal_or_unverified(guidance_asst_msg) is True
