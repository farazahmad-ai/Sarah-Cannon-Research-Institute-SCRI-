"""FastAPI route handlers for landmark clinical trials and protocol chunks.

Provides:
- GET /api/trials: List trials with optional disease category or status filter.
- GET /api/trials/{nct_id}: Retrieve full trial detail with all structured protocol chunks.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import TrialChunkOut, TrialDetail, TrialSummary
from app.auth.jwt import AuthenticatedUser, get_current_user
from app.database.session import get_db_session
from app.database.trials import get_trial_with_chunks, list_trials

logger = logging.getLogger(__name__)

trials_router = APIRouter(prefix="/trials", tags=["trials"])


@trials_router.get(
    "",
    response_model=list[TrialSummary],
    summary="List landmark clinical trials",
    description="Retrieve all active landmark clinical trials with optional category filtering.",
)
async def get_trials(
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    category: Annotated[
        str | None,
        Query(
            description="Target tumor category, e.g. breast_cancer, non_small_cell_lung_cancer, melanoma",
        ),
    ] = None,
    trial_status: Annotated[
        str | None,
        Query(
            alias="status",
            description="Recruitment status, e.g. RECRUITING, ACTIVE_NOT_RECRUITING",
        ),
    ] = None,
) -> list[TrialSummary]:
    """Return trial summaries matching optional category or status filters."""
    trials = await list_trials(session, category=category, status=trial_status)
    return [TrialSummary.model_validate(t) for t in trials]


@trials_router.get(
    "/{nct_id}",
    response_model=TrialDetail,
    summary="Get clinical trial detail with protocol chunks",
    description="Retrieve complete protocol metadata and all structured chunks for a specific trial.",
)
async def get_trial_by_nct_id(
    nct_id: str,
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrialDetail:
    """Return full protocol detail and criteria chunks for coordinator cross-referencing."""
    trial = await get_trial_with_chunks(session, nct_id)
    if trial is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clinical trial {nct_id.upper()} not found.",
        )

    chunks = [
        TrialChunkOut(
            id=c.id,
            nct_id=c.nct_id,
            section_type=c.section_type,
            section_title=c.section_title,
            chunk_index=c.chunk_index,
            chunk_text=c.chunk_text,
            token_count=c.token_count,
        )
        for c in (trial.chunks or [])
    ]

    return TrialDetail(
        nct_id=trial.nct_id,
        brief_title=trial.brief_title,
        category=trial.category,
        phases=trial.phases,
        status=trial.status,
        organization=trial.organization,
        start_date=trial.start_date,
        primary_completion_date=trial.primary_completion_date,
        official_title=trial.official_title,
        last_update_posted_date=trial.last_update_posted_date,
        conditions=trial.conditions,
        arms=trial.arms,
        primary_outcomes=trial.primary_outcomes,
        chunks=chunks,
    )
