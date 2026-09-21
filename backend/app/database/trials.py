"""Database query functions for Clinical Trials and Protocol Chunks.

Provides read-only queries for:
- Listing trials filtered optionally by disease category or recruitment status.
- Fetching single trial metadata by NCT ID.
- Fetching full trial detail with all associated protocol chunks for coordinator inspection.
"""

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ClinicalTrial

logger = logging.getLogger(__name__)


async def list_trials(
    session: AsyncSession,
    *,
    category: str | None = None,
    status: str | None = None,
) -> Sequence[ClinicalTrial]:
    """List clinical trials with optional category and recruitment status filtering.

    Ordered deterministically by category ascending, then NCT ID ascending.
    """
    stmt = select(ClinicalTrial)

    if category:
        stmt = stmt.where(ClinicalTrial.category == category)
    if status:
        stmt = stmt.where(ClinicalTrial.status == status)

    stmt = stmt.order_by(ClinicalTrial.category.asc(), ClinicalTrial.nct_id.asc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_trial(
    session: AsyncSession,
    nct_id: str,
) -> ClinicalTrial | None:
    """Fetch single clinical trial metadata by NCT ID."""
    stmt = select(ClinicalTrial).where(ClinicalTrial.nct_id == nct_id.upper())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_trial_with_chunks(
    session: AsyncSession,
    nct_id: str,
) -> ClinicalTrial | None:
    """Fetch single clinical trial with all structured protocol chunks eagerly loaded.

    Chunks are ordered sequentially by chunk_index for linear document reading.
    """
    stmt = (
        select(ClinicalTrial)
        .where(ClinicalTrial.nct_id == nct_id.upper())
        .options(selectinload(ClinicalTrial.chunks))
    )
    result = await session.execute(stmt)
    trial = result.scalar_one_or_none()
    if trial is not None and trial.chunks:
        # Guarantee chunks are strictly sorted by chunk_index
        trial.chunks.sort(key=lambda c: c.chunk_index)
    return trial
