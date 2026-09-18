"""Asynchronous Supabase platform client wrapper for server-side auth and administration.

Provides:
- init_supabase_admin: Coroutine called during FastAPI lifespan boot to eagerly initialize
  and validate the service-role client (Fail-Fast).
- get_supabase_admin: FastAPI dependency getter returning the initialized AsyncClient.
"""

from supabase import AsyncClient, acreate_client
from supabase.lib.client_options import AsyncClientOptions

from app.config import settings

# Module-level singleton reference populated once during FastAPI lifespan startup
_supabase_admin: AsyncClient | None = None


async def init_supabase_admin() -> AsyncClient:
    """Eagerly initialize and validate the administrative Supabase client at application boot.
    
    Why this pattern is necessary:
    1. Fail-Fast: Validates SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY immediately when the
       server boots. If credentials are bad, Uvicorn crashes at startup rather than during a live
       clinical screening session.
    2. Zero Race Conditions: Eager initialization during single-threaded lifespan startup guarantees
       no concurrent thread or coroutine can duplicate the client.
    3. Non-Blocking Async: Uses AsyncClient backed by non-blocking HTTP I/O, ensuring FastAPI's
       event loop is never stalled during JWT signature verification.
    4. Stateless Multi-Tenancy: persist_session=False ensures coordinator sessions are not
       cached across disparate HTTP requests.
    """
    global _supabase_admin
    
    options = AsyncClientOptions(
        persist_session=False,     # Stateless: never cache user sessions on the server
        auto_refresh_token=False,  # Tokens are refreshed on the client, not the backend
        postgrest_client_timeout=10,
    )
    
    _supabase_admin = await acreate_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
        options=options,
    )
    
    return _supabase_admin


def get_supabase_admin() -> AsyncClient:
    """FastAPI dependency yielding the initialized administrative Supabase client.
    
    Raises RuntimeError if accessed before FastAPI lifespan initialization.
    """
    if _supabase_admin is None:
        raise RuntimeError(
            "Supabase administrative client has not been initialized. "
            "Ensure init_supabase_admin() was called during application lifespan startup."
        )
    return _supabase_admin
