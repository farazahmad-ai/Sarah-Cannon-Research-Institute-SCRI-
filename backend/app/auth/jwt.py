"""Supabase JWT verification and authenticated user dependency.

Delegates all token validation (signature, expiry, audience) to Supabase's own
auth.get_user() endpoint rather than performing local JWT decoding. This avoids
the need to manage Supabase's rotating signing keys inside application code.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import AsyncClient, AuthApiError

from app.database.supabase import get_supabase_admin

# Registered as an OpenAPI security scheme — adds the 🔒 lock icon to all
# protected routes in /docs and enforces Bearer extraction natively.
# auto_error=True means FastAPI returns 403 automatically on a missing header
# before our dependency body even runs.
bearer_scheme = HTTPBearer(auto_error=True)


class AuthenticatedUser(BaseModel):
    """Verified identity extracted from a valid Supabase JWT.

    Populated exclusively from data returned by Supabase auth — never
    constructed from raw token claims inside application code.
    """

    id: str    # Supabase auth UUID — matches profiles.id and chat_threads.user_id
    email: str # Institutional email, e.g. coordinator@scri.com
    role: str  # Supabase role string, typically "authenticated"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    supabase: AsyncClient = Depends(get_supabase_admin),
) -> AuthenticatedUser:
    """FastAPI dependency that verifies a Supabase JWT and returns the caller's identity.

    Flow:
    1. HTTPBearer extracts and validates the Bearer token from the Authorization
       header. Missing or malformed headers are rejected before this body runs.
    2. Delegate token validation to supabase.auth.get_user() — Supabase checks
       the JWT signature against its own keys and verifies expiry server-side.
    3. Return a typed AuthenticatedUser so route handlers never touch raw dicts.

    Raises:
        HTTP 403: Authorization header missing or not Bearer scheme (HTTPBearer).
        HTTP 401: Token present but expired, revoked, or invalid (Supabase).
    """
    token = credentials.credentials

    try:
        response = await supabase.auth.get_user(token)
    except AuthApiError as exc:
        # AuthApiError is raised by the Supabase SDK for invalid/expired tokens.
        # Catch explicitly so a bad token returns a clean 401, not a 500.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc.message}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if response is None or response.user is None:
        # Defensive: SDK returned successfully but no user object was present.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = response.user

    return AuthenticatedUser(
        id=str(user.id),
        email=user.email or "",
        role=user.role or "authenticated",
    )
