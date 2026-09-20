"""Semantic vector search over trial_chunks using pgvector cosine distance."""

from __future__ import annotations

import logging
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import ProtocolPassage
from app.config import settings
from app.database.models import ClinicalTrial, TrialChunk
from app.retrieval.embeddings import embed_texts

logger = logging.getLogger(__name__)

# Default top-k candidate depth for vector search before fusion
VECTOR_TOP_K: int = 50


async def vector_search(
    session: AsyncSession,
    query: str,
    *,
    disease_category: Optional[str] = None,
    nct_id: Optional[str] = None,
    limit: int = VECTOR_TOP_K,
) -> list[ProtocolPassage]:
    """Execute dense semantic vector search against trial_chunks.embedding.

    Args:
        session: Active SQLAlchemy AsyncSession.
        query: Coordinator query or clinical phrasing.
        disease_category: Optional snake_case tumor type filter (e.g. 'non_small_cell_lung_cancer').
        nct_id: Optional NCT ID filter (e.g. 'NCT07659782').
        limit: Number of candidate passages to retrieve.

    Returns:
        List of ProtocolPassage objects ordered by cosine similarity descending.
    """
    if not query.strip():
        return []

    # 1. Generate query embedding using the shared embedding service
    vectors = await embed_texts([query.strip()])
    if not vectors or not vectors[0]:
        logger.warning("Failed to generate embedding for query: %s", query)
        return []

    query_vec = vectors[0]
    expected_dim = settings.OPENAI_EMBEDDING_DIMENSIONS
    if len(query_vec) != expected_dim:
        raise ValueError(
            f"Query vector dimension mismatch: expected {expected_dim}, got {len(query_vec)}"
        )

    # 2. Build pgvector cosine distance query with optional metadata filters
    # Distance <=> is in [0, 2]; cosine similarity is 1 - distance
    distance_expr = TrialChunk.embedding.cosine_distance(query_vec).label("distance")

    stmt = (
        select(
            TrialChunk,
            ClinicalTrial.brief_title,
            ClinicalTrial.last_update_posted_date,
            distance_expr,
        )
        .join(ClinicalTrial, TrialChunk.nct_id == ClinicalTrial.nct_id)
        .where(TrialChunk.embedding.is_not(None))
    )

    if disease_category:
        stmt = stmt.where(ClinicalTrial.category == disease_category)

    if nct_id:
        stmt = stmt.where(TrialChunk.nct_id == nct_id)

    stmt = stmt.order_by(distance_expr.asc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    passages: list[ProtocolPassage] = []
    for chunk, brief_title, last_update_posted_date, distance in rows:
        similarity = max(0.0, 1.0 - float(distance)) if distance is not None else None
        passages.append(
            ProtocolPassage(
                chunk_id=chunk.id,
                nct_id=chunk.nct_id,
                section_type=chunk.section_type,
                section_header=chunk.section_header,
                chunk_text=chunk.chunk_text,
                similarity=similarity,
                last_update_posted_date=last_update_posted_date,
                brief_title=brief_title,
            )
        )

    return passages
