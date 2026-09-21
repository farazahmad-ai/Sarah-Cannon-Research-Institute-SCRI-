"""Main application entrypoint for Sarah Cannon Research Institute (SCRI) Oncology Copilot.

This module initializes the FastAPI application instance, configures CORS middleware
for the React/Vite frontend, and defines fundamental health and diagnostic endpoints.
All configuration parameters are pulled directly from `app.config.settings`.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.database import init_supabase_admin


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events.
    
    Why lifespan context manager is necessary:
    In oncology clinical copilot systems, we must ensure external gateways
    (database pools, embedding services, vector indexes) are initialized cleanly
    before handling coordinator traffic, and gracefully closed upon termination.
    """
    # Startup phase: Log environment status and verify active settings
    print(f"[STARTUP] Starting {settings.APP_NAME} in [{settings.ENVIRONMENT}] mode")
    print(f"[CONFIG] Primary LLM: {settings.OPENAI_CHAT_MODEL} | Embedding: {settings.OPENAI_EMBEDDING_MODEL}")
    print(f"[SECURITY] Allowed CORS Origins: {settings.ALLOWED_ORIGINS}")
    
    # Eagerly initialize and validate Supabase AsyncClient (Fail-Fast)
    await init_supabase_admin()
    print("[AUTH] Supabase AsyncClient initialized successfully (persist_session=False)")
    
    yield  # Application is running and serving requests
    
    # Shutdown phase: Clean up connection pools and background tasks
    print(f"[SHUTDOWN] Shutting down {settings.APP_NAME}...")


def create_application() -> FastAPI:
    """Factory function to build and configure the FastAPI application instance.
    
    Why factory pattern is used:
    Simplifies testing by allowing test suites (pytest) to instantiate isolated
    app instances with overridden dependencies or mock settings if needed.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "AI-powered Clinical Trial Protocol Assistant for Sarah Cannon Research Institute (SCRI). "
            "Provides grounded, citation-backed answers to oncology trial inclusion/exclusion screening."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" or settings.DEBUG else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" or settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Configure Cross-Origin Resource Sharing (CORS)
    # Super necessary: Browser security forbids Vite SPA (e.g. localhost:5173) from calling
    # the backend API unless explicit Access-Control-Allow-* headers are granted.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)

    return application


app = create_application()


@app.get(
    "/health",
    tags=["Health"],
    summary="Application Health Check",
    status_code=status.HTTP_200_OK,
    response_model=dict[str, Any],
)
async def health_check() -> dict[str, Any]:
    """Return health and status diagnostics for the copilot backend.
    
    Used by load balancers, container health monitors (Railway/Docker),
    and frontend ping checks to verify API availability.
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "chat_model": settings.OPENAI_CHAT_MODEL,
        "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
    }


@app.get(
    "/",
    tags=["Root"],
    summary="API Root Information",
    status_code=status.HTTP_200_OK,
    response_model=dict[str, str],
)
async def root() -> dict[str, str]:
    """Root endpoint welcoming clients and directing them to OpenAPI documentation."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG or settings.ENVIRONMENT == "development",
    )
