"""Unified hybrid retrieval orchestrator combining pgvector and PostgreSQL FTS."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import ProtocolPassage
from app.retrieval.fts_search import FTS_TOP_K, fts_search
from app.retrieval.rrf import RRF_K, reciprocal_rank_fusion
from app.retrieval.vector_search import VECTOR_TOP_K, vector_search

logger = logging.getLogger(__name__)

# Default top-k passages returned to the chat orchestrator
DEFAULT_LIMIT: int = 8

# Default minimum cosine similarity floor for vector relevance
DEFAULT_MIN_SIMILARITY: float = 0.30


def apply_similarity_floor(
    passages: list[ProtocolPassage],
    floor: float | None,
    *,
    vector_search_healthy: bool = True,
) -> list[ProtocolPassage]:
    """Filter candidate passages by similarity floor to enforce protocol silence.

    Rules:
      1. If floor is None, all passages are accepted.
      2. When vector_search_healthy is True:
         - A passage must have a known cosine similarity (similarity is not None).
         - That similarity must meet or exceed the floor (similarity >= floor).
         - Pure lexical hits (similarity is None) that did not place in the top 50
           vector results are excluded because their semantic relevance is unverified.
      3. When vector_search_healthy is False (embedding API outage fallback C5):
         - Lexical passages (similarity is None) are preserved so the system does not
           completely blind the coordinator during third-party embedding outages.
    """
    if floor is None:
        return passages

    filtered: list[ProtocolPassage] = []
    for p in passages:
        if p.similarity is not None:
            if p.similarity >= floor:
                filtered.append(p)
        elif not vector_search_healthy:
            # Embedding outage resilience: accept FTS hits when vector search was unavailable
            filtered.append(p)

    return filtered


async def retrieve_protocols(
    session: AsyncSession,
    query: str,
    *,
    disease_category: str | None = None,
    limit: int = DEFAULT_LIMIT,
    min_similarity: float | None = DEFAULT_MIN_SIMILARITY,
) -> list[ProtocolPassage]:
    """Retrieve grounded clinical protocol passages using hybrid search.

    Workflow:
      1. Run vector_search (pgvector cosine similarity) and fts_search (Postgres FTS)
         SEQUENTIALLY on the provided session (concurrency safety B3).
      2. If embedding generation fails, resiliently continue with FTS results.
      3. Fuse candidate rankings using Reciprocal Rank Fusion (RRF, k=60).
      4. Apply similarity floor for protocol silence / abstention signal.
      5. Return top `limit` passages.

    Args:
        session: Active SQLAlchemy AsyncSession.
        query: Coordinator screening query.
        disease_category: Optional snake_case disease filter (e.g. 'non_small_cell_lung_cancer').
        limit: Number of top fused passages to return (default 8).
        min_similarity: Optional cosine similarity floor (defaults to DEFAULT_MIN_SIMILARITY=0.30).

    Returns:
        List of ProtocolPassage objects sorted by fused relevance.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    # Step 1: Sequential retrieval (B3 - never asyncio.gather on AsyncSession)
    vector_search_healthy = True
    vector_passages: list[ProtocolPassage] = []
    try:
        vector_passages = await vector_search(
            session,
            cleaned_query,
            disease_category=disease_category,
            limit=VECTOR_TOP_K,
        )
    except Exception as exc:  # noqa: BLE001
        # Resilience: if embedding service fails, log warning and continue FTS-only (C5)
        vector_search_healthy = False
        logger.warning("Vector search failed during hybrid retrieval; falling back to FTS: %s", exc)

    fts_passages: list[ProtocolPassage] = []
    try:
        fts_passages = await fts_search(
            session,
            cleaned_query,
            disease_category=disease_category,
            limit=FTS_TOP_K,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("FTS search failed during hybrid retrieval: %s", exc)

    if not vector_passages and not fts_passages:
        return []

    # Step 2: Index passages by chunk_id
    # Prefer vector passage if present because it contains cosine similarity
    passages_by_id: dict[uuid.UUID, ProtocolPassage] = {}
    for p in fts_passages:
        passages_by_id[p.chunk_id] = p
    for p in vector_passages:
        passages_by_id[p.chunk_id] = p

    # Step 3: Reciprocal Rank Fusion (k=60)
    ranked_lists = [
        [p.chunk_id for p in vector_passages],
        [p.chunk_id for p in fts_passages],
    ]
    fused_ranked = reciprocal_rank_fusion(ranked_lists, k=RRF_K)

    # Step 4: Assemble fused candidates and apply similarity floor (B5)
    candidates: list[ProtocolPassage] = []
    for chunk_id, _fused_score in fused_ranked:
        passage = passages_by_id.get(chunk_id)
        if passage:
            candidates.append(passage)

    fused_passages = apply_similarity_floor(
        candidates,
        min_similarity,
        vector_search_healthy=vector_search_healthy,
    )

    return fused_passages[:limit]

