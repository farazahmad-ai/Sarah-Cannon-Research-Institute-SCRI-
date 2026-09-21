"""Tests for Clinical Trials database queries and response schemas."""

import uuid
from datetime import date

import pytest

from app.assistant.schemas import CitationOut, MessageOut, TrialChunkOut, TrialDetail, TrialSummary
from app.database.session import async_session_factory, engine
from app.database.trials import get_trial_with_chunks, list_trials


@pytest.fixture
async def cleanup_db_pool():
    yield
    await engine.dispose()



def test_trial_schemas():
    """Verify TrialSummary and TrialDetail serialization contracts."""
    summary = TrialSummary(
        nct_id="NCT07659782",
        brief_title="Study of Investigational KRAS Inhibitor in NSCLC",
        category="non_small_cell_lung_cancer",
        phases=["PHASE1", "PHASE2"],
        status="RECRUITING",
        organization="Sarah Cannon Research Institute",
        start_date=date(2025, 1, 15),
        primary_completion_date=date(2027, 6, 30),
    )
    assert summary.nct_id == "NCT07659782"
    assert summary.category == "non_small_cell_lung_cancer"

    detail = TrialDetail(
        **summary.model_dump(),
        official_title="A Phase 1/2 Study of KRAS Inhibitor",
        conditions=["Non-Small Cell Lung Cancer"],
        arms=[{"label": "Arm A", "type": "Experimental"}],
        chunks=[
            TrialChunkOut(
                id=uuid.uuid4(),
                nct_id="NCT07659782",
                section_type="ELIGIBILITY_EXCLUSION",
                section_title="Eligibility: Exclusion Criterion #4",
                chunk_index=4,
                chunk_text="Prior chemotherapy within 4 weeks.",
                token_count=12,
            )
        ],
    )
    assert detail.official_title is not None
    assert len(detail.chunks) == 1
    assert detail.chunks[0].chunk_index == 4


def test_message_out_with_citations():
    """Verify MessageOut incorporates grounded citations."""
    citation = CitationOut(
        id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        nct_id="NCT07659782",
        section_header="Eligibility: Exclusion Criterion #4",
        verbatim_quote="Prior chemotherapy within 4 weeks.",
        citation_index=1,
    )
    msg = MessageOut(
        id=citation.message_id,
        thread_id=uuid.uuid4(),
        role="assistant",
        content="Prior chemo requires 4-week washout [NCT07659782, Exclusion Criterion #4].",
        created_at=date(2026, 9, 21),
        citations=[citation],
    )
    assert len(msg.citations) == 1
    assert msg.citations[0].nct_id == "NCT07659782"
    assert msg.citations[0].citation_index == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_live_list_trials_and_detail(cleanup_db_pool):
    """Integration test against live Supabase: verify trials and protocol chunks."""
    async with async_session_factory() as session:
        trials = await list_trials(session)
        assert len(trials) == 25

        # Verify category filter
        nsclc_trials = await list_trials(session, category="non_small_cell_lung_cancer")
        assert len(nsclc_trials) > 0
        assert all(t.category == "non_small_cell_lung_cancer" for t in nsclc_trials)

        # Verify get_trial_with_chunks
        first_nct = trials[0].nct_id
        trial_with_chunks = await get_trial_with_chunks(session, first_nct)
        assert trial_with_chunks is not None
        assert len(trial_with_chunks.chunks) > 0
        # Ensure chunks are ordered by chunk_index
        indices = [c.chunk_index for c in trial_with_chunks.chunks]
        assert indices == sorted(indices)
