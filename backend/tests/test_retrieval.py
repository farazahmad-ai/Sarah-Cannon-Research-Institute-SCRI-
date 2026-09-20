"""Integration tests for hybrid retrieval engine against live Supabase database.

Marked with @pytest.mark.integration. These tests require:
- Live Supabase database connection
- OpenRouter / OpenAI API key for text-embedding-3-small embeddings

Run with:
    uv run python -m pytest tests/test_retrieval.py -m integration
"""

import pytest
from sqlalchemy import select

from app.database.models import TrialChunk
from app.database.session import async_session_factory, engine
from app.retrieval.hybrid import retrieve_protocols


@pytest.fixture(autouse=True)
async def cleanup_db_pool():
    yield
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.anyio
async def test_kras_g12d_mutation_retrieval():
    """KRAS G12D query must return NCT07659782 in the top 3 results."""
    async with async_session_factory() as session:
        passages = await retrieve_protocols(session, "KRAS G12D mutation", limit=5)
        assert len(passages) > 0, "Expected at least one passage for KRAS G12D"

        top_3_ncts = [p.nct_id for p in passages[:3]]
        assert "NCT07659782" in top_3_ncts, (
            f"Expected NCT07659782 in top 3, got {top_3_ncts}"
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_washout_period_retrieval():
    """Washout query must return relevant trials with washout criteria in top 5."""
    async with async_session_factory() as session:
        passages = await retrieve_protocols(
            session,
            "prior anti-cancer therapy washout period",
            limit=5,
        )
        assert len(passages) > 0

        # At least one returned passage must discuss prior therapy or washout
        text_corpus = " ".join([p.chunk_text.lower() for p in passages])
        assert "washout" in text_corpus or "prior" in text_corpus or "therapy" in text_corpus


@pytest.mark.integration
@pytest.mark.anyio
async def test_exclusion_criterion_labeling_in_db():
    """Exclusion query must return passages branded as 'Exclusion' and NOT 'Inclusion'.

    Guards against D-1 regression at the database and retrieval layer.
    """
    async with async_session_factory() as session:
        # Query for an exclusion criterion on NCT07297667 (one of the 5 fixed trials)
        passages = await retrieve_protocols(
            session,
            "active central nervous system CNS brain metastases",
            limit=5,
        )
        assert len(passages) > 0

        exclusion_passages = [
            p for p in passages if p.section_type == "ELIGIBILITY_EXCLUSION"
        ]
        assert len(exclusion_passages) > 0, (
            "Expected at least one ELIGIBILITY_EXCLUSION passage for CNS metastases query"
        )

        for p in exclusion_passages:
            assert "Exclusion" in p.section_header
            assert "Inclusion" not in p.section_header


@pytest.mark.integration
@pytest.mark.anyio
async def test_abstention_on_irrelevant_query():
    """Completely irrelevant non-oncology query must return empty list under similarity floor."""
    async with async_session_factory() as session:
        passages = await retrieve_protocols(
            session,
            "pediatric ebola hemorrhagic fever vaccination schedule in primates",
            limit=5,
            min_similarity=0.45,
        )
        assert len(passages) == 0, (
            f"Expected 0 passages for irrelevant query, got {len(passages)}"
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_all_retrieved_chunk_ids_exist_in_db():
    """Every chunk_id returned by retrieval must genuinely exist in trial_chunks."""
    async with async_session_factory() as session:
        passages = await retrieve_protocols(
            session,
            "HER2 positive breast cancer trastuzumab deruxtecan",
            limit=8,
        )
        assert len(passages) > 0

        chunk_ids = [p.chunk_id for p in passages]
        stmt = select(TrialChunk.id).where(TrialChunk.id.in_(chunk_ids))
        result = await session.execute(stmt)
        existing_ids = set(result.scalars().all())

        for cid in chunk_ids:
            assert cid in existing_ids, f"Retrieved chunk_id {cid} does not exist in DB"
