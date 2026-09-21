# SCRI Oncology Copilot — Backend Service

The FastAPI backend API for the **Sarah Cannon Research Institute (SCRI) Oncology Copilot**. It provides grounded, citation-enforced clinical trial protocol screening for Clinical Research Coordinators (CRCs) and Principal Investigators.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) package manager installed

### 2. Environment Setup
Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
```

Ensure the following variables are configured in `.env`:
* `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
* `DATABASE_URL` (Direct session port 5432)
* `OPENAI_API_KEY` (or `OPENROUTER_API_KEY`)

### 3. Install Dependencies
Sync dependencies into the local virtual environment:
```bash
uv sync
```

---

## 🏃 Running the Application

### Development Server (with hot reload)
```bash
uv run python -m uvicorn app.main:app --reload --port 8000
```
*or directly via Python:*
```bash
uv run python -m app.main
```

### Endpoints & Documentation
Once the server is running:
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint:** [http://localhost:8000/health](http://localhost:8000/health)
- **API Root:** [http://localhost:8000/](http://localhost:8000/)

---

## 🧪 Testing & Code Quality

### Run Unit Tests
```bash
uv run pytest
```

### Run Linters & Formatter
```bash
# Check code style
uv run ruff check .

# Automatically fix lint issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

---

## 🗄️ Database Migrations (Alembic)

Database schema is tracked using Alembic against Supabase Postgres (`pgvector` enabled):

```bash
# Check current migration revision
uv run alembic current

# Apply all pending migrations to database
uv run alembic upgrade head

# Generate a new migration after editing SQLAlchemy models
uv run alembic revision --autogenerate -m "add_table_or_field_name"

# Rollback one migration step
uv run alembic downgrade -1
```

---

## 📦 Dependency Management

Always use `uv` to maintain pinned, deterministic dependencies:

```bash
# Add a production package
uv add <package-name>

# Add a development package
uv add --dev <package-name>

# Lock and sync environment
uv sync
```

---

## 🛡️ Architecture Conventions

- **Single Source of Truth:** Never call `os.getenv()` or `load_dotenv()` directly in code; always import `settings` from `app.config`.
- **Fail-Fast Configuration:** The application validates all required keys at startup and halts immediately if secrets are missing.
- **Async by Default:** All FastAPI route handlers, database calls, and AI network requests must use `async def`.
