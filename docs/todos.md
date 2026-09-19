# Sarah Cannon Research Institute (SCRI) — Oncology Copilot Implementation Checklist & Roadmap

This checklist outlines the logical, end-to-end execution sequence to build **SCRI Oncology Copilot** for **Sarah Cannon Research Institute (SCRI)** based on the system architecture and project brief.

---

## 🎯 Recommended Execution Strategy: **Prerequisites ➔ Data ➔ Backend ➔ Frontend ➔ Evaluation**

### Why this sequence?
1. **The Grounding Rule:** In clinical oncology RAG, the UI is an interactive presentation layer for retrieved evidence. Building the schema, section-aware chunker, and hybrid retrieval engine first allows verification against real clinical protocols before writing React code.
2. **Deterministic Verification:** We can test that complex clinical queries (washouts, lab thresholds, biomarker criteria) return exact citable clauses using fast Python unit tests.
3. **Zero Rework:** When connecting the frontend, the backend endpoints are already live, typed, and streaming real verbatim protocol citations.

---

## Phase 0: Prerequisites & Environment Setup (Completed ✅)
- [x] **0.1 Runtime Tooling Verification:**
  - Python 3.12+ installed (`python --version`)
  - `uv` package manager installed (`uv --version`)
  - Node.js 20+ LTS installed (`node --version`)
  - `pnpm` package manager installed (`pnpm --version`)
- [x] **0.2 Cloud Services & Credentials:**
  - Hosted Supabase project created (`bvbitihrufkccmpjvqqp`)
  - Supabase database connection string obtained (Direct session port 5432 & pooler port 6543)
  - Supabase project URL, Anon Key, and Service Role Key obtained
  - OpenRouter API Key provisioned with access to `openai/gpt-4o` and `openai/text-embedding-3-small`
  - Created `backend/.env` and `frontend/.env`

---

## Phase 1: Data Acquisition & Trial Corpus (Completed ✅)
- [x] **1.1 ClinicalTrials.gov Downloader Script:**
  - File: `data/download.py`
  - Built download script targeting 5 core SCRI disease areas (Breast, Lung, Colorectal, Melanoma, Hematologic)
  - Configured `sort: LastUpdatePostDate:desc` to fetch the freshest active protocol amendments
  - Extracted clinical dates (`LAST UPDATE POSTED`, `START DATE`, `PRIMARY COMPLETION`), drug arms, and endpoints
- [x] **1.2 Download Landmark Protocols & Generate Registry:**
  - Directory: `data/downloads/`
  - File: `data/downloads/manifest.json`
  - Downloaded 25 landmark trials with full raw JSON and human-readable protocol text

---

## Phase 2: Database Foundation & Schema Migrations (in `backend/`)

- [ ] **2.1 Backend Scaffolding & Packaging Setup:**
  - [x] Configure `backend/pyproject.toml` with project name `scri-copilot-backend`, Hatchling build system, and dependencies
  - [x] Create `backend/app/__init__.py` (Root application package)
  - [ ] Scaffold internal module directories and empty `__init__.py` files:
    - `backend/app/api/` (FastAPI route handlers)
    - `backend/app/assistant/` (PydanticAI agent, prompts, and dependencies)
    - `backend/app/auth/` (Supabase JWT verification)
    - `backend/app/chat/` (Chat turn orchestration & streaming)
    - `backend/app/database/` (SQLAlchemy models and session helpers)
    - `backend/app/grounding/` (Citation and grounding validator)
    - `backend/app/ingest/` (Chunking and trial ingestion pipeline)
    - `backend/app/retrieval/` (pgvector, full-text search, and RRF fusion)
    - `backend/tests/` (Pytest test suite)

- [x] **2.2 Centralized Environment Settings:**
  - [x] File: `backend/app/config.py`
  - Implement single-source-of-truth `Settings` class using `pydantic-settings`
  - Fail-fast validation for `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`
  - OpenRouter adapter: automatic fallback to `OPENROUTER_API_KEY`, setting `base_url` and `openai/` model prefixes
  - Properties: `effective_api_key`, `effective_base_url`, `sync_database_url` (for Alembic), and `async_database_url` (for SQLAlchemy)
  - Verified live connection to OpenRouter embeddings and chat completions

- [x] **2.3 Database Engine, Session & Supabase Platform Client:**
  - [x] File: `backend/app/database/__init__.py`
  - [x] File: `backend/app/database/session.py`:
    - Configure SQLAlchemy 2.0 `create_async_engine` using `settings.async_database_url`
    - Configure `async_sessionmaker` for non-blocking database transactions
    - Create FastAPI dependency `get_db_session()` for route handlers
  - [x] File: `backend/app/database/base.py`:
    - Declarative `Base` with common timestamp mixins (`created_at`, `updated_at`)
  - [x] File: `backend/app/database/supabase.py`:
    - Asynchronous administrative client wrapper using native `AsyncClient` and `acreate_client`
    - Configured with `AsyncClientOptions(persist_session=False, auto_refresh_token=False)` for stateless multi-tenant request isolation
    - Eager `init_supabase_admin()` in FastAPI lifespan for fail-fast credential validation and zero race conditions
    - FastAPI dependency getter `get_supabase_admin()` returning the initialized `AsyncClient`

- [x] **2.4 SQLAlchemy Declarative Models:**
  - [x] File: `backend/app/database/models.py`:
    - `Profile` model: User identity linked to Supabase auth (`id`, `email`, `full_name`, `role`, timestamps)
    - `ClinicalTrial` model: Landmark trial metadata (`nct_id` PK, `brief_title`, `official_title`, `brief_summary`, `disease_category`, `phase`, `study_type`, `lead_sponsor`, `overall_status`, `start_date`, `primary_completion_date`, `last_update_posted_date`, `study_arms`, `primary_outcomes`, `secondary_outcomes`)
    - `TrialChunk` model: Structured protocol chunks (`id` UUID PK, `nct_id` FK, `section_type`, `section_title`, `chunk_index`, `chunk_text`, `embedding` `Vector(1536)`, `search_vector` `TSVector`, `token_count`, `metadata`)
    - `ChatThread` model: Chat conversation threads (`id` UUID PK, `user_id` FK, `title`, timestamps)
    - `ChatMessage` model: Chat turn messages (`id` UUID PK, `thread_id` FK, `role`, `content`, `metadata`, timestamps)
    - `MessageCitation` model: Grounded citations (`id` UUID PK, `message_id` FK, `chunk_id` FK, `nct_id`, `section_header`, `verbatim_quote`, `citation_index`)

- [x] **2.5 Alembic Migrations Setup & Execution:**
  - [x] Configure `backend/alembic.ini` and `backend/alembic/`
  - [x] File: `backend/alembic/env.py`:
    - Import `app.database.models.Base.metadata`
    - Configure direct connection URL from `settings.sync_database_url`
  - [x] Generate initial migration script: `backend/alembic/versions/0001_create_initial_oncology_schema.py`
  - [x] Customize migration with explicit PostgreSQL extensions and specialized indexes:
    - `CREATE EXTENSION IF NOT EXISTS vector;`
    - HNSW index on `trial_chunks.embedding` using `vector_cosine_ops` (`m=16, ef_construction=64`)
    - GIN index on `trial_chunks.search_vector`
    - Full-text search trigger/generated column: `to_tsvector('english', chunk_text)`
  - [x] Apply migrations to hosted Supabase database: `uv run alembic upgrade head`

---

## Phase 3: Ingestion, Chunking & Embedding Pipeline (in `backend/app/ingest`)

- [ ] **3.1 Section-Aware Protocol Chunker:**
  - [ ] File: `backend/app/ingest/__init__.py`
  - [ ] File: `backend/app/ingest/chunker.py`:
    - Split protocols along clinical boundaries (Study Design, Arms/Interventions, Inclusion Criteria, Exclusion Criteria, Endpoints)
    - Preserve numbered criteria, lab limits (ANC, platelets, CrCl), and prior therapy washout intervals within individual chunks
    - Include trial header context (NCT ID, amendment date, brief title) on every chunk for retrieval preservation
    - Enforce token ceiling (400–600 tokens per chunk) with semantic boundary preservation

- [ ] **3.2 Embedding Generation Service:**
  - [ ] File: `backend/app/retrieval/embeddings.py`:
    - Async client for batch embedding generation using `openai/text-embedding-3-small` (1536 dims)
    - Retry logic with exponential backoff and rate-limit handling

- [ ] **3.3 Ingestion Pipeline Script:**
  - [ ] File: `backend/app/ingest/pipeline.py`:
    - CLI runner to iterate `data/downloads/manifest.json`
    - Parse all 25 downloaded clinical trials, extract metadata, chunk sections, generate embeddings
    - Upsert trials into `clinical_trials` table and chunks into `trial_chunks` table in Supabase
    - Validate row counts, embedding dimensions, and index health

---

## Phase 4: Hybrid Retrieval Engine (in `backend/app/retrieval`)

- [ ] **4.1 Semantic Vector Search:**
  - [ ] File: `backend/app/retrieval/vector_search.py`:
    - Cosine similarity matching (`<=>`) against `trial_chunks.embedding` using `pgvector`
    - Optional metadata filtering by disease category or NCT ID

- [ ] **4.2 Postgres Full-Text Search:**
  - [ ] File: `backend/app/retrieval/fts_search.py`:
    - Exact medical keyword matching using `websearch_to_tsquery` against `trial_chunks.search_vector`
    - Preserves exact oncology terms: *KRAS G12D*, *EGFR Exon 20*, *HER2-low*, *ANC*, *DLT*, *washout*

- [ ] **4.3 Reciprocal Rank Fusion (RRF):**
  - [ ] File: `backend/app/retrieval/rrf.py`:
    - In-memory RRF fusion algorithm combining semantic and lexical score rankings ($k=60$)
    - Normalizes scores and yields top-k deduplicated passages

- [ ] **4.4 Hybrid Retrieval Orchestrator:**
  - [ ] File: `backend/app/retrieval/hybrid.py`:
    - Unified `retrieve_protocols(query, disease_category=None, limit=8)` function
    - Fetches top passages with trial metadata and section titles

- [ ] **4.5 Retrieval Verification Test Suite:**
  - [ ] File: `backend/tests/test_retrieval.py`:
    - Pytest suite verifying biomarker queries, lab limit queries, and washout period queries
    - Asserts that target landmark NCT IDs appear in top 3 retrieved results

---

## Phase 5: PydanticAI Agent & Citation Grounding Gate (in `backend/app/assistant`)

- [ ] **5.1 PydanticAI Schemas & Dependencies:**
  - [ ] File: `backend/app/assistant/schemas.py`:
    - Pydantic models: `GroundedAnswer`, `Citation`, `ProtocolPassage`, `ChatRequest`, `ChatResponseDelta`
  - [ ] File: `backend/app/assistant/deps.py`:
    - `OncologyAgentDeps` holding DB session, user session, hybrid retriever instance, and settings

- [ ] **5.2 Clinical System Prompt & Agent:**
  - [ ] File: `backend/app/assistant/prompts.py`:
    - Oncology system prompt with strict negative constraints
    - Explicit instruction: *"If the protocol does not state a criterion, explicitly state: 'The protocol does not state [X].'"*
    - Mandatory bracketed citation formatting: `[NCTxxxxxxx, Section Title: Criterion #]`
  - [ ] File: `backend/app/assistant/agent.py`:
    - PydanticAI agent configuration with `openai/gpt-4o` and structured dependencies

- [ ] **5.3 Grounding & Citation Validator:**
  - [ ] File: `backend/app/grounding/validator.py`:
    - Post-processing validator ensuring every citation references a chunk that was actually retrieved
    - Validates verbatim quote matches the source chunk text
    - Strips or flags any hallucinated or ungrounded claims

- [ ] **5.4 FastAPI Endpoints & Streaming SSE:**
  - [ ] File: `backend/app/auth/jwt.py`:
    - Supabase JWT token verification and `get_current_user` FastAPI dependency
  - [ ] File: `backend/app/chat/orchestrator.py`:
    - Handles chat turn lifecycle: persists user message, retrieves chunks, runs PydanticAI agent, persists assistant response and citations
  - [ ] File: `backend/app/api/chat.py`:
    - `POST /api/chat/stream`: Server-Sent Events (SSE) streaming endpoint compatible with Vercel AI SDK
    - `GET /api/chat/threads`: List past user chat threads
    - `GET /api/chat/threads/{thread_id}/messages`: Fetch message history with citations
  - [ ] File: `backend/app/api/trials.py`:
    - `GET /api/trials`: List 25 landmark trials with metadata
    - `GET /api/trials/{nct_id}`: Full protocol inspector endpoint
  - [x] File: `backend/app/api/router.py`:
    - Central API router registering all feature sub-routers under `/api` prefix
    - `GET /api/me`: Smoke-test endpoint returning `AuthenticatedUser` (proves end-to-end JWT chain)
  - [x] File: `backend/app/main.py`:
    - FastAPI app factory, CORS middleware, lifespan events, healthcheck route (`GET /health`)
    - Mounts `api_router` from `app.api.router`

---

## Phase 6: Frontend Clinical UI (in `frontend/`)

- [x] **6.1 Scaffolding & Build Tooling:**
  - [x] Initialize Vite + React 19 Single Page Application with TypeScript (`pnpm create vite . --template react-ts`)
  - [x] File: `frontend/package.json`:
    - Dependencies: `@ai-sdk/react`, `@supabase/supabase-js`, `react-router-dom`, `lucide-react`, `clsx`, `tailwind-merge`, `@base-ui/react`
    - Dev dependencies: `tailwindcss` (v4), `@tailwindcss/vite`
  - [x] File: `frontend/vite.config.ts`: Vite build configuration with `@tailwindcss/vite` and `@/*` alias
  - [x] File: `frontend/src/index.css`: Tailwind CSS v4 directives and Nova theme tokens
  - [x] Initialize shadcn/ui with Base UI Nova preset (`components.json`, `src/lib/utils.ts`, `src/components/ui/button.tsx`)


- [x] **6.2 Environment, Auth Client & Login Page:**
  - [x] File: `frontend/src/lib/env.ts`: Single source of truth for frontend environment variables (`VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)
  - [x] File: `frontend/src/lib/supabase.ts`: Supabase browser client (singleton, `persistSession: true`, `autoRefreshToken: true`)
  - [x] File: `frontend/src/lib/api.ts`: Fetch wrapper that automatically attaches the Supabase session JWT to outbound requests; typed `api.me()`, `api.trials.*`, `api.chat.*` helpers
  - [x] File: `frontend/src/context/AuthContext.tsx`: Institutional email auth session provider
  - [x] File: `frontend/src/pages/Login.tsx`: Clinical login screen with email + password (`signInWithPassword`)
  - [x] File: `frontend/src/components/ProtectedRoute.tsx`: Redirect unauthenticated users to `/login`
  - [x] File: `frontend/src/App.tsx`: React Router wired with `AuthProvider`, `/login` route, and protected `/` route
  - [x] File: `frontend/src/pages/Dashboard.tsx`: Auth smoke-test screen — calls `GET /api/me` and displays backend-verified identity

- [ ] **6.4 Clinical Chat Interface:**
  - [ ] File: `frontend/src/components/chat/ChatContainer.tsx`: Streaming conversation view using Vercel AI SDK `useChat`
  - [ ] File: `frontend/src/components/chat/ChatMessage.tsx`: Markdown message renderer with inline interactive citation pill badges
  - [ ] File: `frontend/src/components/chat/ChatInput.tsx`: Prompt composer with quick coordinator screening suggestions (washout rules, biomarker eligibility, lab limits)

- [ ] **6.5 Interactive Evidence Inspection & Citation Popovers:**
  - [ ] File: `frontend/src/components/citations/CitationPill.tsx`: Clickable badge (`[NCT07659782, Exclusion #4]`)
  - [ ] File: `frontend/src/components/citations/CitationPopover.tsx`: Popover drawer displaying verbatim quote, NCT ID, section header, and protocol amendment date

- [ ] **6.6 Protocol Viewer & Trial Catalog:**
  - [ ] File: `frontend/src/components/trials/TrialCard.tsx`: Trial summary card showing disease category, sponsor, phase, and status
  - [ ] File: `frontend/src/components/trials/TrialList.tsx`: Filterable catalog of the 25 landmark trials by disease category
  - [ ] File: `frontend/src/components/trials/TrialDetailDrawer.tsx`: Full protocol viewer drawer for cross-referencing criteria
  - [ ] File: `frontend/src/pages/Dashboard.tsx`: Main split-screen workspace (chat stream on left, protocol drawer / evidence inspector on right)

---

## Phase 7: Benchmark Evaluation & Deployment

- [ ] **7.1 Clinical Benchmark Verification:**
  - [ ] File: `backend/tests/test_clinical_benchmarks.py`:
    - Run the 10 real-world coordinator screening benchmark questions from the project brief
    - Verify 100% citation grounding (0 hallucinated criteria)
    - Verify negative refusal behavior on protocol silence queries
- [ ] **7.2 Deployment Configuration:**
  - [ ] File: `backend/Dockerfile`: FastAPI Uvicorn container
  - [ ] File: `frontend/Dockerfile` & `frontend/nginx.conf`: Vite static build served via Nginx
  - [ ] File: `railway.toml`: Containerized orchestration for Railway deployment
