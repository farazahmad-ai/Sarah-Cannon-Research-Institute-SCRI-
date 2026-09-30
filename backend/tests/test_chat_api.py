"""Unit tests for Chat API endpoints, tenancy rules, and serialization contracts.

Covers Finding M3:
- Enforces tenancy: user A cannot access or delete user B's thread.
- Verifies ThreadOut, MessageOut, CitationOut schemas with last_update_posted_date.
- Verifies unauthenticated requests are rejected.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.assistant.schemas import CitationOut, MessageOut, ThreadOut
from app.database.chats import get_thread
from app.database.models import ChatThread
from app.main import app


def test_thread_and_citation_schemas():
    """Verify ThreadOut, MessageOut, and CitationOut include amendment date."""
    cid = uuid.uuid4()
    mid = uuid.uuid4()
    tid = uuid.uuid4()

    citation = CitationOut(
        id=cid,
        message_id=mid,
        chunk_id=uuid.uuid4(),
        nct_id="NCT05794958",
        section_header="Eligibility: Exclusion Criterion #4",
        verbatim_quote="Washout period is 28 days.",
        citation_index=1,
        last_update_posted_date=date(2024, 3, 15),
        created_at=datetime.now(UTC),
    )

    assert citation.last_update_posted_date == date(2024, 3, 15)

    msg = MessageOut(
        id=mid,
        thread_id=tid,
        role="assistant",
        content="Grounded clinical response [NCT05794958, Exclusion #4].",
        created_at=datetime.now(UTC),
        citations=[citation],
    )
    assert len(msg.citations) == 1
    assert msg.citations[0].last_update_posted_date == date(2024, 3, 15)

    thread = ThreadOut(
        id=tid,
        title="Screening for Lung Cancer",
        created_at=datetime.now(UTC),
    )
    assert thread.id == tid
    assert thread.title == "Screening for Lung Cancer"


@pytest.mark.anyio
async def test_unauthenticated_request_rejected():
    """Request without Supabase bearer token must be rejected with 401 or 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/chat/threads")
        assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_tenancy_ownership_enforcement_raises_permission_error():
    """Accessing a thread belonging to another user must raise PermissionError (403)."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    # Mock thread belonging to User B
    foreign_thread = ChatThread(
        id=thread_id,
        user_id=user_b_id,
        title="User B Private Screening Session",
    )

    class MockAsyncSession:
        async def execute(self, stmt):
            class MockResult:
                def scalar_one_or_none(self):
                    return foreign_thread
            return MockResult()

    mock_session = MockAsyncSession()

    # User A tries to access User B's thread -> MUST raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        await get_thread(mock_session, thread_id, user_a_id)

    assert "Access denied: thread belongs to another coordinator." in str(exc_info.value)


def test_message_feedback_schema():
    """Verify MessageFeedbackPayload and MessageOut metadata_json serialization."""
    from app.assistant.schemas import MessageFeedbackPayload

    payload = MessageFeedbackPayload(rating="helpful", comment="Clear explanation of washout.")
    assert payload.rating == "helpful"
    assert payload.comment == "Clear explanation of washout."

    msg = MessageOut(
        id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        role="assistant",
        content="Evidence response.",
        created_at=datetime.now(UTC),
        metadata_json={"feedback": {"rating": "helpful"}},
    )
    assert msg.metadata_json is not None
    assert msg.metadata_json["feedback"]["rating"] == "helpful"


@pytest.mark.anyio
async def test_record_message_feedback_tenancy():
    """Feedback on a message belonging to another user must raise PermissionError."""
    from app.database.chats import record_message_feedback
    from app.database.models import ChatMessage

    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    mock_msg = ChatMessage(
        id=msg_id,
        thread_id=thread_id,
        role="assistant",
        content="Response",
    )

    class MockFeedbackSession:
        async def execute(self, stmt):
            class MockResult:
                def __init__(self, val):
                    self.val = val
                def scalar_one_or_none(self):
                    return self.val
            # Check query intent:
            stmt_str = str(stmt)
            if "chat_messages" in stmt_str:
                return MockResult(mock_msg)
            # Thread query: belongs to user_b
            return MockResult(user_b_id)

    mock_session = MockFeedbackSession()

    # User A tries to give feedback on User B's thread message
    with pytest.raises(PermissionError) as exc_info:
        await record_message_feedback(mock_session, msg_id, user_a_id, "helpful")

    assert "Access denied: message belongs to another coordinator's thread." in str(exc_info.value)

