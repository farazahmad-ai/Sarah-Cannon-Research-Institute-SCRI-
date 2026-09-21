"""Configuration module for Sarah Cannon Research Institute (SCRI) Oncology Copilot.

This module is the SINGLE SOURCE OF TRUTH for application settings and environment variables.
Never call `os.getenv()` or `load_dotenv()` directly in application code.
Fails fast on startup if critical configuration keys are missing.
"""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with fail-fast validation.
    
    Why Pydantic Settings is super necessary:
    - In clinical oncology, silent configuration errors (e.g., missing API keys or wrong DB hosts)
      could lead to dangerous runtime failures while a coordinator is screening a cancer patient.
    - Pydantic Settings validates data types and presence at startup, guaranteeing that if the
      FastAPI server boots, all required credentials and endpoints are guaranteed to exist.
    """

    # --- Pydantic Settings Behavior Configuration ---
    model_config = SettingsConfigDict(
        # Automatically load environment variables from the backend/.env file
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore extra/unused environment variables instead of crashing
        extra="ignore",
        # Allow case-insensitive environment variable matching (e.g. database_url or DATABASE_URL)
        case_sensitive=False,
    )

    # --- Application Metadata & Server Execution ---
    # Used for OpenAPI / Swagger documentation and healthcheck endpoints
    APP_NAME: str = "SCRI Oncology Copilot"
    # Controls environment mode (development, staging, production)
    ENVIRONMENT: str = "development"
    # When True, enables detailed exception tracebacks in responses (keep False in production)
    DEBUG: bool = False
    # Network interface to bind Uvicorn (0.0.0.0 allows containerized access on Railway/Docker)
    HOST: str = "0.0.0.0"
    # Port on which the FastAPI application listens
    PORT: int = 8000

    # --- CORS (Cross-Origin Resource Sharing) Configuration ---
    # Super necessary: Browsers block Vite SPA (localhost:5173) from calling FastAPI (localhost:8000)
    # unless explicit CORS headers are sent. This setting defines which frontend origins are trusted.
    ALLOWED_ORIGINS: list[str] | str = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- Supabase Platform Credentials ---
    # Why Supabase is used:
    # 1. Manages institutional auth sessions for Clinical Research Coordinators (CRCs) and PIs.
    # 2. Hosts PostgreSQL database with the `pgvector` extension for trial protocol embeddings.
    
    # Project URL used for Supabase API requests and auth token verification
    SUPABASE_URL: str = Field(..., description="Supabase project URL (e.g. https://<ref>.supabase.co)")
    
    # Publishable anon key (safe for client browsers, used for auth handshakes)
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase publishable anon key")
    
    # Administrative secret key with full database privileges.
    # Super necessary: Allows backend to verify JWT tokens and perform administrative tasks.
    # CRITICAL: Never expose this key to frontend or Git.
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ..., description="Supabase administrative service role secret key"
    )

    # --- Database Connection (PostgreSQL with pgvector) ---
    # Super necessary: Used by Alembic migrations and SQLAlchemy ORM models.
    # Note: Must point to the direct/session connection (port 5432), NOT the transaction pooler (port 6543),
    # because Alembic DDL migrations require session-level locks and vector extensions.
    DATABASE_URL: str = Field(
        ...,
        description="Direct PostgreSQL session connection string (port 5432) for Alembic and SQLAlchemy",
    )
    # Optional raw password stored for script utilities or external database tooling
    DATABASE_PASSWORD: str | None = None

    # --- AI, Embeddings & Large Language Model Gateway ---
    # Why this dual setup is super necessary:
    # Supports direct OpenAI API keys OR OpenRouter keys interchangeably without code changes.
    OPENAI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    
    # Base URL for API requests. Defaults to OpenRouter gateway if OPENROUTER_API_KEY is detected.
    OPENAI_BASE_URL: str | None = None
    
    # Primary reasoning LLM for clinical eligibility checking and citation synthesis.
    # Uses GPT-4o for clinical reasoning and strict negative constraint adherence (anti-hallucination).
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    
    # Embedding model used to convert clinical trial protocol sections into dense semantic vectors.
    # text-embedding-3-small generates 1536-dimensional vectors optimized for medical retrieval.
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Vector dimensionality (1536) matching pgvector column definition: vector(1536)
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536

    # --- Validators ---

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list[str]) -> list[str]:
        """Convert comma-separated origin strings from .env into a clean Python list.
        
        Why this is super necessary:
        In .env files, origins are often written as a comma-separated string:
        `ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000`
        FastAPI's CORSMiddleware expects a typed `list[str]`, so this validator normalizes it.
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_and_resolve_ai_keys(self) -> "Settings":
        """Fail fast if no valid LLM API key is provided and configure OpenRouter routing.
        
        Why this validator is super necessary:
        1. Fail Fast: If an engineer or container starts the backend without ANY AI key,
           we crash immediately with an informative message rather than failing 20 minutes later
           when a clinical research coordinator submits a trial query.
        2. OpenRouter Adapter: Automatically sets the base URL (`https://openrouter.ai/api/v1`)
           and attaches vendor prefixes (`openai/gpt-4o`, `openai/text-embedding-3-small`)
           so OpenRouter routes requests to the correct model endpoints.
        """
        if not self.OPENAI_API_KEY and not self.OPENROUTER_API_KEY:
            raise ValueError(
                "Missing LLM API Key: Either OPENAI_API_KEY or OPENROUTER_API_KEY must be provided in backend/.env."
            )

        # If OpenRouter key is provided without direct OpenAI key, route via OpenRouter
        if not self.OPENAI_API_KEY and self.OPENROUTER_API_KEY:
            if not self.OPENAI_BASE_URL:
                self.OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
            
            # Ensure model identifiers include the vendor prefix required by OpenRouter
            if self.OPENAI_CHAT_MODEL == "gpt-4o":
                self.OPENAI_CHAT_MODEL = "openai/gpt-4o"
            if self.OPENAI_EMBEDDING_MODEL == "text-embedding-3-small":
                self.OPENAI_EMBEDDING_MODEL = "openai/text-embedding-3-small"

        return self

    # --- Helper Properties for Clean Architecture ---

    @property
    def effective_api_key(self) -> str:
        """Return whichever API key is active (OpenAI or OpenRouter).
        
        Why this is super necessary:
        Eliminates repetitive `if settings.OPENAI_API_KEY else settings.OPENROUTER_API_KEY`
        boilerplate throughout the ingestion, retrieval, and assistant modules.
        """
        return self.OPENAI_API_KEY or self.OPENROUTER_API_KEY or ""

    @property
    def effective_base_url(self) -> str | None:
        """Return the active base URL for API requests (e.g. OpenRouter or default OpenAI)."""
        return self.OPENAI_BASE_URL

    @property
    def sync_database_url(self) -> str:
        """Return synchronous PostgreSQL connection string for Alembic migrations and psycopg.
        
        Why this is super necessary:
        Alembic migration scripts and synchronous PostgreSQL tools require driver scheme
        `postgresql://` (or `postgresql+psycopg://`). If the URL has `postgres://` or `asyncpg`,
        this property normalizes it to prevent driver connection errors.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def async_database_url(self) -> str:
        """Return asynchronous PostgreSQL connection string for SQLAlchemy async engine.
        
        Why this is super necessary:
        FastAPI async route handlers and non-blocking database queries use `asyncpg`.
        SQLAlchemy requires the connection string scheme to explicitly be `postgresql+asyncpg://`.
        This property converts standard `postgresql://` strings automatically.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of validated Settings.
    
    Why @lru_cache is super necessary:
    Reading and parsing `.env` files from disk is an I/O operation. Caching the parsed
    Settings instance ensures `.env` is read only once during application boot, providing
    instant memory access on all subsequent dependency injections and requests.
    """
    return Settings()


# Global settings singleton for single-source-of-truth access across the entire application
settings = get_settings()
