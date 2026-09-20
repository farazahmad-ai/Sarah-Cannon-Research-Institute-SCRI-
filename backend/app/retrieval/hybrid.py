"""Unified hybrid retrieval orchestrator combining pgvector and PostgreSQL FTS."""

from __future__ import annotations

import logging
from typing import Optional
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


async def retrieve_protocols(
    session: AsyncSession,
    query: str,
    *,
    disease_category: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    min_similarity: Optional[float] = None,
) -> list[ProtocolPassage]:
    """Retrieve grounded clinical protocol passages using hybrid search.

    Workflow:
      1. Run vector_search (pgvector cosine similarity) and fts_search (Postgres FTS)
         SEQUENTIALLY on the provided session (concurrency safety B3).
      2. If embedding generation fails, resiliently continue with FTS results.
      3. Fuse candidate rankings using Reciprocal Rank Fusion (RRF, k=60).
      4. Apply optional similarity floor for protocol silence / abstention signal.
      5. Return top `limit` passages.

    Args:
        session: Active SQLAlchemy AsyncSession.
        query: Coordinator screening query.
        disease_category: Optional snake_case disease filter (e.g. 'non_small_cell_lung_cancer').
        limit: Number of top fused passages to return (default 8).
        min_similarity: Optional cosine similarity floor (e.g. 0.30).

    Returns:
        List of ProtocolPassage objects sorted by fused relevance.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    # Step 1: Sequential retrieval (B3 - never asyncio.gather on AsyncSession)
    vector_passages: list[ProtocolPassage] = []
    try:
        vector_passages = await vector_search(
            session,
            cleaned_query,
            disease_category=disease_category,
            limit=VECTOR_TOP_K,
        )
    except Exception as exc:
        # Resilience: if embedding service fails, log warning and continue FTS-only (C5)
        logger.warning("Vector search failed during hybrid retrieval; falling back to FTS: %s", exc)

    fts_passages: list[ProtocolPassage] = []
    try:
        fts_passages = await fts_search(
            session,
            cleaned_query,
            disease_category=disease_category,
            limit=FTS_TOP_K,
        )
    except Exception as exc:
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

    # Step 4: Assemble fused passages and apply similarity floor if requested
    fused_passages: list[ProtocolPassage] = []
    floor = min_similarity

    for chunk_id, fused_score in fused_ranked:
        passage = passages_by_id.get(chunk_id)
        if not passage:
            continue

        # If similarity floor is specified and passage has similarity, check floor
        if floor is not None and passage.similarity is not None and passage.similarity < floor:
            continue

        fused_passages.append(passage)
        if len(fused_passages) >= limit:
            break

    return fused_passages
