"""Unit tests for Reciprocal Rank Fusion (RRF) algorithm."""

import math
import uuid

from app.retrieval.rrf import reciprocal_rank_fusion


def test_empty_inputs():
    """Empty list of lists or lists of empty lists return empty output."""
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_single_list_order_and_scores():
    """Single list produces descending 1/(k+rank) scores."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()

    result = reciprocal_rank_fusion([[id1, id2, id3]], k=60)

    assert len(result) == 3
    assert result[0] == (id1, 1.0 / 61.0)
    assert result[1] == (id2, 1.0 / 62.0)
    assert result[2] == (id3, 1.0 / 63.0)


def test_two_lists_summation_and_deduplication():
    """Chunk appearing in both lists gets the sum of its reciprocal rank scores."""
    common_id = uuid.uuid4()  # Rank 1 in list 1, Rank 2 in list 2
    unique1 = uuid.uuid4()    # Rank 2 in list 1
    unique2 = uuid.uuid4()    # Rank 1 in list 2

    list1 = [common_id, unique1]
    list2 = [unique2, common_id]

    result = reciprocal_rank_fusion([list1, list2], k=60)

    # common_id score: 1/61 + 1/62 = 0.0163934 + 0.0161290 = 0.0325224
    expected_common = (1.0 / 61.0) + (1.0 / 62.0)
    # unique2 score: 1/61 = 0.0163934
    expected_u2 = 1.0 / 61.0
    # unique1 score: 1/62 = 0.0161290
    expected_u1 = 1.0 / 62.0

    assert len(result) == 3
    assert result[0][0] == common_id
    assert math.isclose(result[0][1], expected_common, rel_tol=1e-6)

    assert result[1][0] == unique2
    assert math.isclose(result[1][1], expected_u2, rel_tol=1e-6)

    assert result[2][0] == unique1
    assert math.isclose(result[2][1], expected_u1, rel_tol=1e-6)


def test_deterministic_tie_breaking():
    """Ties in score are broken deterministically by chunk_id string representation."""
    id_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_b = uuid.UUID("00000000-0000-0000-0000-000000000002")

    # Both are rank 1 in their respective single-element lists
    # list 1: [id_b] -> score = 1/61
    # list 2: [id_a] -> score = 1/61
    result = reciprocal_rank_fusion([[id_b], [id_a]], k=60)

    assert len(result) == 2
    assert math.isclose(result[0][1], result[1][1])
    # Tie broken by str(chunk_id): id_a ("...01") comes before id_b ("...02")
    assert result[0][0] == id_a
    assert result[1][0] == id_b


def test_custom_k():
    """Custom k parameter scales reciprocal scores properly."""
    id1 = uuid.uuid4()
    result = reciprocal_rank_fusion([[id1]], k=10)
    assert len(result) == 1
    assert result[0] == (id1, 1.0 / 11.0)
