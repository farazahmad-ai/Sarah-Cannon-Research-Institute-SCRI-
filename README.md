# Sarah Cannon Research Institute (SCRI) — Oncology Copilot

An internal AI clinical research assistant that allows Clinical Research Coordinators (CRCs), Molecular Tumor Board navigators, and oncology investigators to query complex clinical trial protocols in plain English and receive sourced, citable answers with zero hallucinations.

## The Client

**Sarah Cannon Research Institute (SCRI)** is one of the world's leading oncology research organizations and clinical trial networks, conducting clinical trials across more than 250 oncology clinic sites. 

Coordinators and investigators spend 15–20 hours per week manually opening and cross-referencing 100+ page clinical trial protocols to screen cancer patients against complex inclusion/exclusion criteria. The SCRI Oncology Copilot automates that protocol intake and verification work so clinicians can match patients to life-saving therapies faster and with total confidence.

Full clinical case study & brief: [docs/project-brief.md](docs/project-brief.md)

## Stack

| Layer | Choice |
| :--- | :--- |
| Backend | Python 3.12+ / FastAPI / PydanticAI |
| Frontend | Vite + React SPA + TypeScript |
| Database | Supabase Postgres (users, chats, trial protocols, chunks) |
| Migrations | SQLAlchemy models + Alembic |
| Retrieval | Supabase `pgvector` + Postgres full-text search (RRF fusion) |
| Auth | Supabase Auth (institutional email) |
| Hosting | Render (backend Web Service + frontend Static Site) |
| LLM + embeddings | OpenAI / OpenRouter (`text-embedding-3-small` + `gpt-4o`) |

## Repo Layout

```text
Sarah Cannon Research Institute (SCRI)/
├── AGENTS.md                          # Source of truth for agents (read first)
├── README.md                          # Overview, stack, setup, and quickstart
├── .gitignore                         # Git exclusion rules
├── data/                              # Trial protocol corpus + download pipeline
│   ├── download.py                    # ClinicalTrials.gov REST API v2 downloader
│   └── downloads/                     # Local protocol JSONs & manifest (gitignored)
├── docs/                              # Architecture, case study brief, guide, and todos
│   ├── architecture.md                # System diagrams, data flow, and schemas
│   ├── project-brief.md               # Real-world clinical case study & requirements
│   ├── guide.md                       # Comprehensive setup & deployment guide
│   └── todos.md                       # Step-by-step implementation checklist
├── backend/                           # FastAPI service
│   ├── alembic/                       # Database migrations
│   ├── app/                           # FastAPI app & database models
│   ├── pyproject.toml                 # Backend dependencies & packaging
│   ├── README.md                      # Backend operations guide
│   └── AGENTS.md                      # Backend agent instructions
└── frontend/                          # Vite + React SPA
    ├── src/                           # Components, pages, and lib
    ├── package.json                   # Frontend dependencies
    └── AGENTS.md                      # Frontend agent instructions
```

## Prerequisites

| Tool | Version | Used for |
| :--- | :--- | :--- |
| Python | 3.12+ | Backend runtime |
| uv | latest | Fast Python package management and script execution |
| Node.js | 20+ (LTS) | Frontend runtime |
| pnpm | latest | Frontend package manager |

External services needed:
1. **Supabase:** Hosted Postgres database with `pgvector` and Supabase Auth.
2. **OpenAI / OpenRouter API Key:** For generating vector embeddings (`text-embedding-3-small`) and grounded answers (`gpt-4o`).

## Sample Clinical Trial Protocol Data

Fetch the curated sample of active oncology trial protocols from the public **ClinicalTrials.gov REST API v2**:

```bash
uv run data/download.py
```

By default, this queries the latest landmark interventional oncology trials across 5 core SCRI disease areas (NSCLC, Lymphoma/CAR-T, Colorectal, Breast, and Melanoma), saves structured protocol JSONs and readable text documents under `data/downloads/`, and generates `data/downloads/manifest.json`.

---

## 🚀 How to Run the Application

To run the entire system locally, you will run the **Backend API** in one terminal and the **Frontend SPA** in a second terminal.

### ⚡ Quick Reference (At a Glance)

| Service | Directory | First-Time Setup | Run Command | Default URL |
| :--- | :--- | :--- | :--- | :--- |
| **Backend API** | `backend/` | `cp .env.example .env`<br>`uv sync`<br>`uv run python -m alembic upgrade head` | `uv run python -m uvicorn app.main:app --reload --port 8000` | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Frontend SPA** | `frontend/` | `cp .env.example .env`<br>`pnpm install` | `pnpm dev` | [http://localhost:5173](http://localhost:5173) |
| **Trial Ingestion** | `backend/` | `uv run data/download.py` | `uv run python -m app.ingest.pipeline` | _Seeds Supabase pgvector_ |

---

### Step 1: Running the Backend (Terminal 1)

#### 1.1 Environment Setup
Navigate to the `backend/` directory and configure your environment file:

```bash
cd backend
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

Configure the following required variables inside `backend/.env`:
- `SUPABASE_URL` — Supabase Project URL (`https://<project-ref>.supabase.co`)
- `SUPABASE_ANON_KEY` — Supabase anon public key
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role secret key
- `DATABASE_URL` — Supabase Postgres direct session connection string (port 5432):
  `postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres`
- `OPENAI_API_KEY` — OpenAI or OpenRouter API key

#### 1.2 Install Dependencies & Apply Database Migrations
```bash
# Sync dependencies into local virtual environment
uv sync

# Run database migrations to provision tables, pgvector extension, and search indexes
uv run python -m alembic upgrade head
```

#### 1.3 (Optional / First Time) Ingest Oncology Clinical Trials
If you need to seed the vector database with landmark clinical trial protocols:
```bash
# From project root: download active trial protocols from ClinicalTrials.gov
uv run data/download.py

# In backend/: chunk protocols, generate embeddings, and upsert to Supabase
uv run python -m app.ingest.pipeline
```

#### 1.4 Start the Backend Server
Run the API server with module mode:

```bash
uv run python -m uvicorn app.main:app --reload --port 8000
```

> [!TIP]
> **Windows Note:** Always use `uv run python -m uvicorn ...` instead of `uv run uvicorn ...`. Direct invocation of the script trampoline on Windows can fail with `error: uv trampoline failed to canonicalize script path`. Running Python module mode (`python -m <module>`) circumvents this issue completely.

*Alternatively, you can run directly:*
```bash
uv run python -m app.main
```

The backend is now live:
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint:** [http://localhost:8000/health](http://localhost:8000/health)

---

### Step 2: Running the Frontend (Terminal 2)

Open a **new terminal** window or tab:

#### 2.1 Environment Setup
Navigate to the `frontend/` directory and configure your environment file:

```bash
cd frontend
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

Verify that `frontend/.env` contains:
```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-key>
```

#### 2.2 Install Dependencies
Install packages using **pnpm** (the mandatory package manager):

```bash
pnpm install
```

#### 2.3 Start the Development Server
```bash
pnpm dev
```

The frontend application will now be running at:
- **Web App:** [http://localhost:5173](http://localhost:5173)

---

## 🛠️ Helpful Development Commands

### Backend
```bash
# Run backend test suite
cd backend
uv run python -m pytest

# Check & format code style
uv run python -m ruff check .
uv run python -m ruff format .

# Create a new Alembic migration after modifying models
uv run python -m alembic revision --autogenerate -m "describe_changes"
```

### Frontend
```bash
cd frontend

# Run TypeScript typecheck without emitting files
pnpm tsc --noEmit

# Run ESLint
pnpm lint

# Build production bundle
pnpm build
```

---

## 📖 Additional Documentation

- [Setup & Architecture Guide](docs/guide.md) — Comprehensive infrastructure and architectural walkthrough.
- [Backend README](backend/README.md) — Detailed backend operations and database guide.
- [Frontend README](frontend/README.md) — Frontend architecture and component standards.
- [Clinical Project Brief](docs/project-brief.md) — Clinical background and requirements.
- [Todos & Roadmap](docs/todos.md) — Implementation roadmap and phase checklist.

