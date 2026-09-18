"""Database session and connection engine management.

Provides:
- engine: SQLAlchemy AsyncEngine configured with PostgreSQL asyncpg driver.
- async_session_factory: Session maker for asynchronous non-blocking transactions.
- get_db_session: FastAPI dependency generator yielding transactional sessions.
"""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


# Configure non-blocking async PostgreSQL engine with connection pooling.
# Super necessary: In production oncology environments, multiple research coordinators
# will query inclusion/exclusion criteria concurrently. Pre-pinging prevents dropped connections
# and pool overflow handles traffic spikes without blocking the FastAPI event loop.
engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,       # Verifies connection liveness before checking out of pool
    pool_size=10,             # Keep up to 10 active connections in pool
    max_overflow=20,          # Allow up to 20 surge connections during high load
    pool_timeout=30,          # Seconds to wait for an available connection before raising error
)

# Thread-safe session factory for spawning async sessions
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Keep model attributes accessible after commit without re-querying
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an asynchronous database session.
    
    Why this pattern is necessary:
    Guarantees each incoming HTTP request receives a dedicated transaction context.
    If an uncaught exception occurs during request execution, the session is
    automatically rolled back before closing to ensure database state integrity.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
