"""Central API router for the SCRI Oncology Copilot backend.

All application routes are registered here and mounted under the /api prefix
in main.py. This keeps main.py clean and allows each feature module to declare
its own sub-router that gets included here.
"""

from fastapi import APIRouter, Depends

from app.auth.jwt import AuthenticatedUser, get_current_user

api_router = APIRouter(prefix="/api")


@api_router.get(
    "/me",
    tags=["Auth"],
    summary="Return verified caller identity",
    response_model=AuthenticatedUser,
)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Smoke-test endpoint — proves the JWT travelled from browser to backend.

    If this returns your email, the full auth chain is working:
    Supabase session → api.ts Bearer injection → FastAPI → jwt.py → Supabase
    validation → AuthenticatedUser.
    """
    return current_user
