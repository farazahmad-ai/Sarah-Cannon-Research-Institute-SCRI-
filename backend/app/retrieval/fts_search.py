"""PostgreSQL full-text search over trial_chunks using websearch_to_tsquery."""

from __future__ import annotations

import logging
from typing import Optional
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import ProtocolPassage
from app.database.models import ClinicalTrial, TrialChunk

logger = logging.getLogger(__name__)

# Default top-k candidate depth for FTS before fusion
FTS_TOP_K: int = 50


async def fts_search(
    session: AsyncSession,
    query: str,
    *,
    disease_category: Optional[str] = None,
    nct_id: Optional[str] = None,
    limit: int = FTS_TOP_K,
) -> list[ProtocolPassage]:
    """Execute lexical full-text search against trial_chunks.search_vector.

    Uses PostgreSQL `websearch_to_tsquery` to safely handle raw coordinator
    clinical phrasing (e.g. 'KRAS G12D', 'EGFR Exon 20') without throwing
    syntax errors on punctuation or unescaped symbols.

    Args:
        session: Active SQLAlchemy AsyncSession.
        query: Coordinator query or clinical phrasing.
        disease_category: Optional snake_case tumor type filter (e.g. 'non_small_cell_lung_cancer').
        nct_id: Optional NCT ID filter (e.g. 'NCT07659782').
        limit: Number of candidate passages to retrieve.

    Returns:
        List of ProtocolPassage objects ordered by ts_rank_cd descending.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    # 1. Build websearch_to_tsquery expression
    ts_query = func.websearch_to_tsquery("english", cleaned_query)

    # 2. Check if the tsquery is empty (e.g. input was entirely stop words like 'in and or')
    num_nodes = (await session.execute(select(func.numnode(ts_query)))).scalar() or 0
    if num_nodes == 0:
        return []

    # 3. Build ranking and filtering expressions
    rank_expr = func.ts_rank_cd(TrialChunk.search_vector, ts_query).label("rank")

    stmt = (
        select(
            TrialChunk,
            ClinicalTrial.brief_title,
            ClinicalTrial.last_update_posted_date,
            rank_expr,
        )
        .join(ClinicalTrial, TrialChunk.nct_id == ClinicalTrial.nct_id)
        .where(TrialChunk.search_vector.op("@@")(ts_query))
    )

    if disease_category:
        stmt = stmt.where(ClinicalTrial.category == disease_category)

    if nct_id:
        stmt = stmt.where(TrialChunk.nct_id == nct_id)

    stmt = stmt.order_by(rank_expr.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    passages: list[ProtocolPassage] = []
    for chunk, brief_title, last_update_posted_date, rank in rows:
        passages.append(
            ProtocolPassage(
                chunk_id=chunk.id,
                nct_id=chunk.nct_id,
                section_type=chunk.section_type,
                section_header=chunk.section_header,
                chunk_text=chunk.chunk_text,
                similarity=None,  # FTS produces lexical rank, not cosine similarity
                last_update_posted_date=last_update_posted_date,
                brief_title=brief_title,
            )
        )

    return passages
