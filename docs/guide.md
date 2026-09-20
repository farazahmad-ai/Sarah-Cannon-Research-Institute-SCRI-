# Sarah Cannon Research Institute (SCRI) — Oncology Copilot Setup Guide

This guide compiles and adapts the end-to-end setup instructions for **SCRI Oncology Copilot** at **Sarah Cannon Research Institute (SCRI)**. It covers the complete provisioning and local development workflow across **Supabase**, the **FastAPI backend**, and the **Vite + React frontend**.

---

## Table of Contents
1. [System Overview & Architecture](#system-overview--architecture)
2. [Supabase Setup (Database & Auth)](#1-supabase-setup)
   - [1.1 Create Account & Project](#11-create-an-account--project)
   - [1.2 Collect Credentials](#12-collect-credentials)
   - [1.3 Auth Settings (Institutional Email Only)](#13-auth-settings-institutional-email-only)
   - [1.4 Database Schema Management (Alembic)](#14-database-schema-management)
3. [Backend Setup (FastAPI & AI Services)](#2-backend-setup)
   - [2.1 Technology Rationale](#21-technology-rationale)
   - [2.2 Initialization (`backend/`)](#22-init-from-backend)
   - [2.3 Database Migrations (Alembic)](#23-database-migrations)
   - [2.4 Running the API Server](#24-run-the-api-server)
   - [2.5 Python Imports & Editable Package](#25-imports-from-app)
   - [2.6 Landmark Oncology Trial Corpus Ingestion](#26-landmark-oncology-trial-corpus-ingestion)
4. [Frontend Setup (Vite + React SPA)](#3-frontend-setup)
   - [3.1 Technology Rationale](#31-technology-rationale)
   - [3.2 Initialization (`frontend/`)](#32-init-from-frontend)
   - [3.3 Running the Development Server](#33-run-the-frontend)
   - [3.4 Type Checking & Linting](#34-type-checking--linting)
5. [Environment Variables Reference](#4-environment-variables-reference)
   - [Backend `.env`](#backend-env)
   - [Frontend `.env`](#frontend-env)
6. [Full Local Development Flow (Verification)](#5-full-local-development-flow)

---

## System Overview & Architecture

**SCRI Oncology Copilot** serves Clinical Research Coordinators (CRCs), Molecular Tumor Board (MTB) navigators, and Principal Investigators across SCRI's network of 250+ community cancer clinics.

- **Frontend:** Vite + React 18+ TypeScript SPA, Tailwind CSS + shadcn/ui, Vercel AI SDK streaming.
- **Backend:** Python 3.12+ / FastAPI, PydanticAI agent orchestration, OpenAI (`gpt-4o` + `text-embedding-3-small`).
- **Database:** Hosted Supabase Postgres with `pgvector` for semantic search and Postgres Full-Text Search (`tsvector`) for exact medical keyword matching.
- **Data Ingestion:** Automated protocol downloader (`data/download.py`) fetching landmark active oncology protocols from ClinicalTrials.gov REST API v2.

---

## 1. Supabase Setup

We use Supabase for **Postgres** (users, chats, clinical trial protocols, chunks, vector embeddings, and citations) and **Auth** (institutional email sign-in). You need one hosted Supabase project before wiring up `backend/` and `frontend/`.

### 1.1 Create an Account & Project

1. Go to [supabase.com](https://supabase.com) and sign up (GitHub or institutional email).
2. Confirm your email if prompted.
3. You will land in the [Supabase Dashboard](https://supabase.com/dashboard). The free tier is sufficient for local development.
4. Open [New Project](https://supabase.com/dashboard/new).
5. Pick your organization (a personal organization is created automatically on first signup).
6. Set a **Project Name** (e.g., `SCRI Oncology Copilot` or `scri-oncology-copilot`).
7. Choose a **Database Password** — save it securely; you need it for direct database connection strings and Alembic migrations.
8. Pick a **Region** close to your location.
9. Click **Create new project** and wait until the status becomes healthy (~1–2 minutes).

---

### 1.2 Collect Credentials

You need these values in your backend and frontend configuration files (`backend/.env` and `frontend/.env`):

| Value | Where to find it in Supabase | Used by | Notes |
| :--- | :--- | :--- | :--- |
| **Project URL** | Dashboard → **Project Settings** → **API** → Project URL | Frontend + Backend | e.g. `https://<ref>.supabase.co` |
| **anon (public) key** | Dashboard → **Project Settings** → **API** → `anon` `public` key | Frontend | Safe to expose in the client browser |
| **service_role (secret) key** | Dashboard → **Project Settings** → **API** → `service_role` `secret` key | Backend only | Full administrative privileges — **never expose to browser or git** |
| **Project ref** | Dashboard URL `supabase.com/dashboard/project/<ref>` or `supabase projects list` | Supabase CLI | Identifies your remote cloud instance |
| **Direct database connection string** | Dashboard → **Project Settings** → **Database** → Connection string (URI, session mode, port 5432) | Backend (Alembic & direct DB access) | Format: `postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres` |
| **Database password** | Set at project creation | Direct Postgres connection | Remember to URL-encode special characters |

From the Supabase CLI, you can also print API keys:

```bash
supabase projects api-keys --project-ref <your-project-ref>
```

> [!WARNING]
> Keep `SUPABASE_SERVICE_ROLE_KEY` out of Git, frontend environment files, and client-side bundles. Only the FastAPI backend should ever access the service role.

---

### 1.3 Auth Settings (Institutional Email Only)

This app uses institutional email authentication only (`@scri.com`, `@hcahealthcare.com`) — no third-party social OAuth (Google, GitHub, etc.).

1. Navigate to **Dashboard** → **Authentication** → **Providers**.
2. Ensure **Email** is enabled.
3. For local development, you may go to **Authentication** → **Email** and toggle off **"Confirm email"** so developer sign-up works immediately without needing inbox verification (re-enable for production).

---

### 1.4 Database Schema Management

**SCRI Oncology Copilot** uses **Alembic** managed from the Python backend for all schema migrations. **Do not create application tables manually in the Supabase dashboard.**

Alembic migrations track and manage:
- The `vector` extension (`create extension if not exists vector`)
- `clinical_trials` metadata table
- `trial_chunks` table containing clinical section text and metadata
- `vector(1536)` embedding columns
- Generated `tsvector` columns for exact medical keyword matching (e.g. *KRAS G12D*, *EGFR Exon 20*, *ANC*)
- HNSW indexes (`vector_cosine_ops`, `m=16, ef_construction=64`) and GIN indexes on `tsvector`
- Chat threads (`chat_threads`), messages (`chat_messages`), and citations (`message_citations`)
- User profiles (`profiles`) table (RLS policies planned for future production hardening)

> [!IMPORTANT]
> Always use the **direct/session database connection string (port 5432)** for Alembic. Do **NOT** use the transaction pooler connection string (port 6543) for running migrations, as migrations require session-level DDL locks.

---

## 2. Backend Setup

### 2.1 Technology Rationale

The backend is built with **Python 3.12+ and FastAPI** because the server is responsible for clinical AI, protocol parsing, and retrieval-augmented generation (RAG), not simple web CRUD. 

Python provides the strongest ecosystem for:
- Clinical trial protocol ingestion from ClinicalTrials.gov REST API v2
- Section-aware chunking preserving inclusion/exclusion criteria, lab limits, and washout periods
- Vector embedding generation (`text-embedding-3-small`)
- Hybrid search execution (`pgvector` cosine similarity + Postgres full-text search)
- In-memory Reciprocal Rank Fusion (RRF)
- Strict grounding and citation validation with PydanticAI and `gpt-4o`

Keeping this logic behind a dedicated FastAPI service leaves the React frontend strictly focused on clinical user experience, streaming UI, and citation popovers.

---

### 2.2 Init (from `backend/`)

To initialize and synchronize dependencies in the `backend/` directory using `uv`:

```bash
cd backend
uv sync
uv add fastapi uvicorn pydantic pydantic-settings httpx structlog openai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector asyncpg
uv add --dev pytest ruff
```

---

### 2.3 Database Migrations

Alembic owns database schema changes for this project. SQLAlchemy models describe the tables, and Alembic migrations apply those changes to Supabase Postgres.

#### Initialize Alembic (executed once from `backend/`):

```bash
uv run alembic init alembic
```

#### Configure `alembic/env.py`:
Ensure `alembic/env.py` imports the app's declarative metadata (`from app.database import Base`) and reads the direct database URL from `app.config.settings.DATABASE_URL`. Always use the direct/session Supabase database connection, not the transaction pooler URL, for migrations.

#### Generate a migration after updating SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "add oncology clinical trials and chat tables"
```

Always review the generated migration script. Add explicit operations for Supabase/Postgres features that autogenerate cannot reliably infer:
- `create extension if not exists vector;`
- `vector(1536)` columns on `trial_chunks`
- Generated `tsvector` columns for full-text search
- HNSW indexes:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_trial_chunks_embedding 
  ON trial_chunks 
  USING hnsw (embedding vector_cosine_ops) 
  WITH (m = 16, ef_construction = 64);
  ```
- GIN indexes for full-text search:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_trial_chunks_fts 
  ON trial_chunks 
  USING gin (search_vector);
  ```
- Row Level Security (RLS) enablement and tenant policies (planned for future production hardening; initial schema uses application-level tenant isolation)

#### Apply migrations:

```bash
uv run alembic upgrade head
```

---

### 2.4 Run the API Server

Run the backend service locally:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

---

### 2.5 Imports (`from app...`)

`backend/app` is installed as an editable package by `uv sync`, so `from app...` imports work reliably from uvicorn, direct Python scripts, automated tests, and Jupyter kernels.

The `[build-system]` and `[tool.hatch.build.targets.wheel]` sections in `backend/pyproject.toml` instruct `uv` how to install the local `app/` package:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

#### Preferred API server command:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

#### Direct file execution:
```bash
cd backend
uv run python app/main.py
```

#### Interactive Exploration / Jupyter:
To run Jupyter notebooks against the backend environment, register the kernel:

```bash
cd backend
uv run python -m ipykernel install --user --name scri-copilot-backend --display-name "SCRI Copilot Backend"
```

Notebooks and test scripts can then import backend modules directly:
```python
from app.config import settings
from app.database import get_db
from app.assistant.agent import oncology_agent
```

---

### 2.6 Landmark Oncology Trial Corpus Ingestion

The SCRI Oncology Copilot relies on 25 landmark clinical trial protocols across 5 core SCRI disease areas (Breast, Lung, Colorectal, Melanoma, Hematologic malignancies).

#### Step 1: Download Landmark Protocols from ClinicalTrials.gov
From the repository root (standard-library script, requires no backend venv):

```bash
uv run data/download.py
```

This fetches active Phase 1–3 protocols with full clinical study sections (eligibility criteria, arms/interventions, outcome measures, sponsor, dates) into `data/downloads/` and generates `data/downloads/manifest.json`.

#### Step 2: Section-Aware Chunking & Vector Upsert
Run the ingestion pipeline to parse sections, generate 1536-dimensional embeddings with `text-embedding-3-small`, and load trials into Supabase:

```bash
cd backend
uv run python -m app.ingest.pipeline
```

---

## 3. Frontend Setup

### 3.1 Technology Rationale

The frontend is built as a **Vite + React 18+ SPA in strict TypeScript** because it is an internal clinical intelligence tool for coordinators and investigators requiring:
- High responsiveness and sub-second UI interactions
- SSE streaming response rendering with citation popovers
- Authenticated app flows using Supabase Auth
- Clean decoupling from the FastAPI backend API

We intentionally avoid SSR, Next.js, or complex server-side node rendering to keep deployment lightweight, containerized, and fast.

---

### 3.2 Init (from `frontend/`)

Initialize the frontend from the `frontend/` directory using **pnpm**:

```bash
cd frontend
pnpm create vite . --template react-ts
pnpm install
pnpm add react-router-dom @supabase/supabase-js ai @ai-sdk/react lucide-react clsx tailwind-merge
pnpm add -D tailwindcss @tailwindcss/vite
pnpm dlx shadcn@latest init
```

> [!NOTE]
> Per workspace standards, **pnpm** is the mandatory package manager for frontend dependencies (`minimum-release-age=10080`). Do not use `npm` or `yarn`. Do not install `axios`, `lodash`, or `moment`.

---

### 3.3 Run the Frontend

Start the Vite development server:

```bash
cd frontend
pnpm install
pnpm dev
```

The frontend will run at `http://localhost:5173`.

---

### 3.4 Type Checking & Linting

Verify TypeScript types and code linting prior to committing:

```bash
cd frontend
pnpm tsc --noEmit
pnpm lint
```

---

## 4. Environment Variables Reference

Configuration values must strictly adhere to the single source of truth rules:
- **Backend:** `backend/app/config.py` (fail-fast startup validation; never call `os.getenv` directly in application logic).
- **Frontend:** `frontend/src/lib/env.ts` (fail-fast validation; never read `import.meta.env` directly in components).

### Backend `.env`

File: `backend/.env` (modeled after [backend/.env.example](file:///g:/My%20Drive/FarazAhmad-ai/projects/Sarah%20Cannon%20Research%20Institute%20%28SCRI%29/backend/.env.example))

```dotenv
# --- Supabase (Auth + API) ---
# Found in: Supabase Dashboard → Project Settings → API
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-secret-key

# --- Postgres (Alembic + Direct Session DB Access) ---
# Found in: Supabase Dashboard → Project Settings → Database → Connection string (URI, session mode, port 5432)
# Do NOT use the transaction pooler URL (pooler.supabase.com:6543) — migrations require a session connection.
DATABASE_URL=postgresql://postgres:your-db-password@db.your-project-ref.supabase.co:5432/postgres

# --- OpenAI (LLM & Embeddings) ---
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536

# --- Server & CORS ---
ALLOWED_ORIGINS=http://localhost:5173
```

### Frontend `.env`

File: `frontend/.env` (modeled after [frontend/.env.example](file:///g:/My%20Drive/FarazAhmad-ai/projects/Sarah%20Cannon%20Research%20Institute%20%28SCRI%29/frontend/.env.example))

```dotenv
# --- Backend API ---
VITE_API_BASE_URL=http://localhost:8000

# --- Supabase (Browser Authentication) ---
# Only browser-safe public values belong here. Never expose service_role or database credentials.
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
```

---

## 5. Full Local Development Flow

When setting up or verifying the entire system locally, follow this sequence:

```bash
# 1. Download landmark clinical trial protocols
uv run data/download.py

# 2. Configure Backend environment
# Copy backend/.env.example to backend/.env and populate credentials

# 3. Apply database migrations to Supabase
cd backend
uv sync
uv run alembic upgrade head

# 4. Ingest trial corpus into Supabase vector database
uv run python -m app.ingest.pipeline

# 5. Start Backend API
uv run uvicorn app.main:app --reload --port 8000

# 6. In a separate terminal, configure and start Frontend SPA
cd ../frontend
# Copy frontend/.env.example to frontend/.env and populate credentials
pnpm install
pnpm dev
```

You can now open `http://localhost:5173` in your browser to sign in and interact with the SCRI Oncology Copilot.
