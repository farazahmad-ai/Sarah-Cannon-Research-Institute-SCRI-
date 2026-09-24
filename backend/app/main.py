"""Main application entrypoint for Sarah Cannon Research Institute (SCRI) Oncology Copilot.

This module initializes the FastAPI application instance, configures CORS middleware
for the React/Vite frontend, and defines fundamental health and diagnostic endpoints.
All configuration parameters are pulled directly from `app.config.settings`.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.database import init_supabase_admin
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events.
    
    Why lifespan context manager is necessary:
    In oncology clinical copilot systems, we must ensure external gateways
    (database pools, embedding services, vector indexes) are initialized cleanly
    before handling coordinator traffic, and gracefully closed upon termination.
    """
    # Startup phase: Log environment status and verify active settings
    # S8: Use structured logging; avoid printing sensitive config (model names, origin list)
    logger.info("Starting %s in [%s] mode", settings.APP_NAME, settings.ENVIRONMENT)
    logger.info("CORS origins configured: %d origin(s)", len(settings.ALLOWED_ORIGINS))
    
    # Eagerly initialize and validate Supabase AsyncClient (Fail-Fast)
    await init_supabase_admin()
    logger.info("Supabase AsyncClient initialized successfully (persist_session=False)")
    
    yield  # Application is running and serving requests
    
    # Shutdown phase: Clean up connection pools and background tasks
    logger.info("Shutting down %s...", settings.APP_NAME)


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
        # S2: Only expose API docs when DEBUG is explicitly True. Environment-name
        # gating was fragile — a typo like "prod" would leak the full schema.
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # S6: Security headers (HSTS, X-Frame-Options, etc.) — registered first so
    # headers are present on every response including CORS preflight.
    application.add_middleware(SecurityHeadersMiddleware)

    # Configure Cross-Origin Resource Sharing (CORS)
    # Super necessary: Browser security forbids Vite SPA (e.g. localhost:5173) from calling
    # the backend API unless explicit Access-Control-Allow-* headers are granted.
    # S1: Restrict to only the HTTP methods and headers the API actually uses,
    # rather than wildcard "*" which widens the attack surface with credentials.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # S4: Per-user rate limiting on LLM-backed endpoints to prevent
    # OpenAI/OpenRouter credit exhaustion from runaway requests.
    application.add_middleware(RateLimitMiddleware)

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
    
    Used by load balancers, container health monitors (Render/Docker),
    and frontend ping checks to verify API availability.
    S3: Stripped internal config (model names, environment) — load balancers
    only need a 200; anonymous visitors don't need our AI provider details.
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
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

    # S5: Require BOTH development environment AND explicit DEBUG flag for
    # hot-reload. Prevents accidental reload in production if started via
    # `python -m` instead of the recommended `uvicorn app.main:app`.
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development" and settings.DEBUG,
    )
