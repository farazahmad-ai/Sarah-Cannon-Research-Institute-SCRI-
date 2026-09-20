"""Reciprocal Rank Fusion (RRF) implementation for hybrid retrieval.

Merges multiple ranked lists of chunk UUIDs into a single deduplicated,
re-ranked list using reciprocal rank scoring:

    score(d) = SUM_{m in models} (1 / (k + rank_m(d)))

where rank is 1-indexed, and k=60 (standard TREC / clinical retrieval constant).
Pure in-memory math with deterministic tie-breaking.
"""

from __future__ import annotations

import uuid
from typing import List, Sequence, Tuple

# Standard RRF smoothing constant spec'd in architecture.md:322
RRF_K: int = 60


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[uuid.UUID]],
    k: int = RRF_K,
) -> List[Tuple[uuid.UUID, float]]:
    """Fuse multiple ranked lists of chunk UUIDs using Reciprocal Rank Fusion.

    Parameters:
        ranked_lists: Sequence of ordered sequences of chunk UUIDs (e.g. [vector_ids, fts_ids]).
                      Each list must be ordered best-first (index 0 is rank 1).
        k: Smoothing constant. Default is 60.

    Returns:
        List of (chunk_id, fused_score) tuples sorted descending by fused_score.
        Ties are broken deterministically by string representation of chunk_id.
    """
    if not ranked_lists:
        return []

    scores: dict[uuid.UUID, float] = {}

    for ranked_list in ranked_lists:
        for rank_zero_idx, chunk_id in enumerate(ranked_list):
            rank = rank_zero_idx + 1  # 1-based rank
            reciprocal_score = 1.0 / (k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + reciprocal_score

    if not scores:
        return []

    # Sort descending by fused score, with deterministic tie-breaking by chunk_id string
    sorted_items = sorted(
        scores.items(),
        key=lambda item: (-item[1], str(item[0])),
    )

    return sorted_items
