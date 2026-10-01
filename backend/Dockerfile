# ==============================================================================
# Multi-stage Dockerfile for Sarah Cannon Research Institute (SCRI) Oncology Copilot
# Optimized for Render deployment, minimal layer size, and dynamic $PORT binding.
# ==============================================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim-bookworm AS builder

# Install official uv binary for fast, frozen dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Enable bytecode compilation and direct copy linking for caching efficiency
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies from frozen lockfile (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code and Alembic migrations
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Install root package into virtual environment
RUN uv sync --frozen --no-dev

# --- Stage 2: Runtime ---
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

# Copy isolated application and pre-built virtual environment from builder
COPY --from=builder /app /app

# Ensure runtime uses the uv-created virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Expose default HTTP port
EXPOSE 8000

# Execute Uvicorn server dynamically binding to Render's assigned $PORT (defaults to 8000)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
