"""Offline unit tests for hybrid retrieval similarity floor and abstention filtering."""

import uuid

from app.assistant.schemas import ProtocolPassage
from app.retrieval.hybrid import apply_similarity_floor


def _make_passage(
    chunk_id: uuid.UUID | None = None,
    similarity: float | None = None,
    nct_id: str = "NCT12345678",
    header: str = "Inclusion Criteria",
    text: str = "Sample criterion text",
) -> ProtocolPassage:
    return ProtocolPassage(
        chunk_id=chunk_id or uuid.uuid4(),
        nct_id=nct_id,
        section_type="ELIGIBILITY_INCLUSION",
        section_header=header,
        chunk_text=text,
        similarity=similarity,
    )


def test_floor_filters_low_similarity():
    """Passages with similarity below floor must be discarded."""
    p_high = _make_passage(similarity=0.75)
    p_mid = _make_passage(similarity=0.35)
    p_low = _make_passage(similarity=0.25)
    p_barely_low = _make_passage(similarity=0.299)

    passages = [p_high, p_mid, p_low, p_barely_low]
    filtered = apply_similarity_floor(passages, floor=0.30, vector_search_healthy=True)

    assert len(filtered) == 2
    assert p_high in filtered
    assert p_mid in filtered
    assert p_low not in filtered
    assert p_barely_low not in filtered


def test_floor_none_allows_all():
    """When floor is None, all passages pass through unconditionally."""
    p1 = _make_passage(similarity=0.10)
    p2 = _make_passage(similarity=None)
    p3 = _make_passage(similarity=0.85)

    passages = [p1, p2, p3]
    filtered = apply_similarity_floor(passages, floor=None)

    assert len(filtered) == 3
    assert filtered == passages


def test_floor_excludes_lexical_only_when_vector_healthy():
    """FTS-only passages (similarity=None) are dropped when vector search is healthy.

    Guards against Finding 2 regression: noisy lexical-only candidates cannot bypass
    the similarity floor.
    """
    p_semantic = _make_passage(similarity=0.65)
    p_lexical_only = _make_passage(similarity=None)

    passages = [p_semantic, p_lexical_only]
    filtered = apply_similarity_floor(passages, floor=0.30, vector_search_healthy=True)

    assert len(filtered) == 1
    assert p_semantic in filtered
    assert p_lexical_only not in filtered


def test_floor_preserves_lexical_only_when_vector_unhealthy():
    """FTS-only passages are preserved when vector search failed (resilience C5)."""
    p_fts1 = _make_passage(similarity=None, text="KRAS G12D mutation confirmed")
    p_fts2 = _make_passage(similarity=None, text="Prior systemic therapy allowed")

    passages = [p_fts1, p_fts2]
    filtered = apply_similarity_floor(passages, floor=0.30, vector_search_healthy=False)

    assert len(filtered) == 2
    assert p_fts1 in filtered
    assert p_fts2 in filtered


def test_all_below_floor_returns_empty_list():
    """When all passages are below floor, an empty list must be returned."""
    p1 = _make_passage(similarity=0.15)
    p2 = _make_passage(similarity=0.20)
    p3 = _make_passage(similarity=None)  # dropped when healthy

    passages = [p1, p2, p3]
    filtered = apply_similarity_floor(passages, floor=0.30, vector_search_healthy=True)

    assert filtered == []
