# Sarah Cannon Research Institute (SCRI) — Oncology Copilot Implementation Checklist & Roadmap

This checklist outlines the logical, end-to-end execution sequence to build **SCRI Oncology Copilot** for **Sarah Cannon Research Institute (SCRI)** based on the system architecture and project brief.

---

## 🎯 Recommended Execution Strategy: **Prerequisites ➔ Data ➔ Backend ➔ Frontend ➔ Evaluation & Deployment ➔ High-Value RAG Enhancements**

### Why this sequence?
1. **The Grounding Rule:** In clinical oncology RAG, the UI is an interactive presentation layer for retrieved evidence. Building the schema, section-aware chunker, and hybrid retrieval engine first allows verification against real clinical protocols before writing React code.
2. **Deterministic Verification:** We can test that complex clinical queries (washouts, lab thresholds, biomarker criteria) return exact citable clauses using fast Python unit tests.
3. **Zero Rework:** When connecting the frontend, the backend endpoints are already live, typed, and streaming real verbatim protocol citations.
4. **Scoped Excellence:** Focus purely on AI/RAG intelligence (Recall@K, MRR, multi-turn context) rather than enterprise HIPAA plumbing.

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
    - [x] `backend/app/api/` (FastAPI route handlers)
    - [ ] `backend/app/assistant/` (PydanticAI agent, prompts, and dependencies)
    - [x] `backend/app/auth/` (Supabase JWT verification)
    - [ ] `backend/app/chat/` (Chat turn orchestration & streaming)
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
  *Audit fix: `session.py` catches `BaseException` to safely rollback on client disconnect.*
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
    - `ClinicalTrial` model: Landmark trial metadata (`nct_id` PK, `category`, `brief_title`, `official_title`, `organization`, `status`, `start_date`, `primary_completion_date`, `last_update_posted_date`, `phases`, `conditions`, `arms`, `primary_outcomes`)
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

## Phase 3: Ingestion, Chunking & Embedding Pipeline (in `backend/app/ingest`) (Completed ✅)

- [x] **3.1 Section-Aware Protocol Chunker:**
  *Audit fix: regex supports "Key Exclusion/Inclusion" & no-colon headers; added numbered list parsing; removed unused token soft cap.*
  - [x] File: `backend/app/ingest/__init__.py`
  - [x] File: `backend/app/ingest/chunker.py`:
    - Custom clinical boundary chunker — pure Python, zero external chunking libraries
    - Navigates JSON key paths directly (`protocolSection.eligibilityModule.eligibilityCriteria`)
    - Each `*` bullet in eligibility criteria becomes its own atomic ChunkPayload
    - Sub-bullets (qualifying conditions) kept attached to parent criterion — never split mid-criterion
    - Context prefix `[NCT ID | Phase | Category]` prepended to embed_text for identity-aware vectors
    - Token estimate via word_count × 1.3 heuristic (no tiktoken dependency)
    - Produces: BRIEF_SUMMARY (1) + STUDY_DESIGN (0-1, where present) + ELIGIBILITY_INCLUSION (N) + ELIGIBILITY_EXCLUSION (N)

- [x] **3.2 Embedding Generation Service:**
  - [x] File: `backend/app/retrieval/__init__.py`
  - [x] File: `backend/app/retrieval/embeddings.py`:
    - Async batched calls to OpenAI-compatible API via OpenRouter (`openai/text-embedding-3-small`)
    - Batch size: 64 texts per API call; exponential backoff on 429/5xx errors (up to 5 retries)
    - Returns `list[list[float]]` — 1536-dim vectors, one per input chunk
    - Dimension sanity check against `settings.OPENAI_EMBEDDING_DIMENSIONS` before DB write

- [x] **3.3 Ingestion Pipeline Script:**
  *Audit fix: re-chunked 25 trials (460 → 563 chunks); `--skip-embed` protects existing embeddings unless `--force`; continue-on-error loop.*
  - [x] File: `backend/app/ingest/pipeline.py`:
    - CLI with staged flags: `--dry-run`, `--limit N`, `--nct-id`, `--one-per-category`, `--skip-embed`
    - Reads `data/downloads/manifest.json`, resolves local JSON paths, calls chunker + embeddings
    - Upserts `clinical_trials` via `ON CONFLICT DO UPDATE` (idempotent re-runs)
    - Deletes + bulk re-inserts `trial_chunks` per trial (clean slate on re-ingest)
    - **Result: 25 trials | 563 chunks | 563 embeddings (dim=1536) committed to Supabase**

---

## Phase 4: Hybrid Retrieval Engine (in `backend/app/retrieval`) (Completed ✅)

### Pre-Phase 4 Gate & Foundation
- [x] **Gate A1 — Embedding Completeness:** `SELECT count(*) FROM trial_chunks WHERE embedding IS NULL` == 0 *(Verified: 563/563 non-null vectors)*
- [x] **Gate A2 — Exclusion Labeling:** `SELECT count(*) FROM trial_chunks WHERE section_type='ELIGIBILITY_EXCLUSION'` == 268 *(Verified: 268 exclusion chunks)*
- [x] **Gate A3 — Working Tree Cleanliness:** Commit all pre-Phase 4 audit fixes so Phase 4 diffs remain isolated and bisectable.
- [x] **Gate A4 — Architectural Decisions Locked:**
  - **B1 (File Names):** `rrf.py` and `hybrid.py` locked across `todos.md` and `architecture.md`.
  - **B2 (Header in FTS):** Migration `0002` will widen `search_vector` trigger to `chunk_text || ' ' || section_header` with a backfill update (no re-embedding required).
  - **B3 (Concurrency Safety):** Sequential execution on single `AsyncSession` — **NEVER** `asyncio.gather` on SQLAlchemy session.
  - **B4 (Constants):** `RRF_K = 60`, `VECTOR_TOP_K = 50`, `FTS_TOP_K = 50`, `DEFAULT_LIMIT = 8`.
  - **B5 (Abstention Floor):** Carry raw cosine similarity (`similarity: float | None`) alongside fused score; caller applies ~0.30 floor, returning `[]` on low confidence to trigger protocol silence refusal.
  - **B6 (Category Filters):** Use real snake_case values from `manifest.json` (`non_small_cell_lung_cancer`, `melanoma`, etc.).

---

### Step-by-Step Implementation Sequence (Ordered Build)

- [x] **Step 1: Pytest Setup, Test Skeleton & Schema Extension:**
  - [x] File: `backend/pyproject.toml`:
    - Add `[tool.pytest.ini_options]` with `integration` marker:
      ```toml
      [tool.pytest.ini_options]
      markers = ["integration: needs live Supabase + embedding API"]
      addopts = "-m 'not integration'"
      ```
  - [x] Create `backend/tests/__init__.py`
  - [x] File: `backend/app/assistant/schemas.py`:
    - Extend `ProtocolPassage` with join key and display fields:
      ```python
      class ProtocolPassage(BaseModel):
          chunk_id: uuid.UUID                  # RRF dedup key & MessageCitation FK (Phase 5.5)
          nct_id: str
          section_type: str                    # ELIGIBILITY_EXCLUSION, etc.
          section_header: str
          chunk_text: str                      # Verbatim quote text
          similarity: float | None = None      # Raw cosine similarity (1 - distance)
          last_update_posted_date: date | None = None
          brief_title: str | None = None
      ```

- [x] **Step 2: Reciprocal Rank Fusion (RRF) & Unit Tests (Pure, Offline):**
  - [x] File: `backend/app/retrieval/rrf.py`:
    - Implement `reciprocal_rank_fusion(ranked_lists: list[list[uuid.UUID]], k: int = 60) -> list[tuple[uuid.UUID, float]]`
    - Returns `(chunk_id, fused_score)` sorted descending, deduplicated
    - Deterministic tie-breaking by `chunk_id`
    - Pure in-memory math, no DB or network I/O
  - [x] File: `backend/tests/test_rrf.py`:
    - Unit tests: hand-computed ranking order, $1/(60+rank)$ calculation, score summation when chunk is in both lists, tie-breaking, empty input handling

- [x] **Step 3: Protocol Chunker Corpus Invariant Tests (Offline):**
  - [x] File: `backend/tests/test_chunker.py`:
    - Offline regression tests over all 25 downloaded JSONs:
      - `total_chunks == 563`
      - Exactly 1 `BRIEF_SUMMARY` per trial
      - Every trial with an exclusion heading produces `ELIGIBILITY_EXCLUSION` chunks (guards against D-1 regression)
      - Numbered lists (`1.`, `1)`) parsed into distinct criteria (guards against D-2 regression)
      - `max(chunk.token_count) <= 1600`
      - Non-empty `section_header` and `chunk_text` on every chunk
      - `(nct_id, chunk_index)` uniqueness

- [x] **Step 4: Migration 0002 — Widen Full-Text Search Trigger:**
  - [x] File: `backend/alembic/versions/0002_widen_fts_trigger_to_include_header.py`:
    - Widen `trial_chunks.search_vector` trigger to `chunk_text || ' ' || section_header`
  - [x] Run `uv run alembic upgrade head`
  - [x] Execute backfill: `UPDATE trial_chunks SET chunk_text = chunk_text;` (seconds-long, no API re-embedding)

- [x] **Step 5: Semantic Vector Search & Postgres Full-Text Search:**
  - [x] File: `backend/app/retrieval/vector_search.py`:
    - `async def vector_search(session: AsyncSession, query: str, *, disease_category: str | None = None, nct_id: str | None = None, limit: int = 50) -> list[ProtocolPassage]`
    - Query embedding via `await embed_texts([query])` (reuse shared service; never hardcode model name)
    - Assert `len(vec) == settings.OPENAI_EMBEDDING_DIMENSIONS`
    - Order by `embedding <=> :vec` (cosine distance); compute `similarity = 1 - distance`
  - [x] File: `backend/app/retrieval/fts_search.py`:
    - `async def fts_search(session: AsyncSession, query: str, *, disease_category: str | None = None, nct_id: str | None = None, limit: int = 50) -> list[ProtocolPassage]`
    - Use `websearch_to_tsquery('english', :q)` to gracefully handle unescaped medical text
    - Order by `ts_rank_cd(search_vector, query)`
    - Return `[]` if `websearch_to_tsquery` yields an empty query (e.g. stop-words)

- [x] **Step 6: Hybrid Retrieval Orchestrator & Chat Integration:**
  - [x] File: `backend/app/retrieval/hybrid.py`:
    - `async def retrieve_protocols(session: AsyncSession, query: str, *, disease_category: str | None = None, limit: int = 8, min_similarity: float | None = None) -> list[ProtocolPassage]`
    - Execute vector and FTS searches sequentially on one session (B3)
    - Fuse candidate pools via `reciprocal_rank_fusion`
    - Enrich fused chunks with single join to `clinical_trials` for `brief_title` and `last_update_posted_date`
    - Resilience: if embedding API fails, log warning and return FTS-only results rather than aborting chat turn
    - Apply `min_similarity` floor (abstention signal for protocol silence)
  - [x] File: `backend/app/chat/orchestrator.py`:
    - Call `retrieve_protocols` inside `pre_session` (while session is open) — NOT after closing
    - Update `build_openai_messages` to accept `passages: list[ProtocolPassage]` and format numbered blocks (`[Passage 1]`, `[Passage 2]`)
    - Delete `_stub_retrieve` and verify no references to `NCT05794958` remain in the codebase

- [x] **Step 7: Retrieval Integration Test Suite & Verification:**
  - [x] File: `backend/tests/test_retrieval.py` (`@pytest.mark.integration`):
    - Target queries: KRAS G12D (NCT07659782 in top 3), washout periods, lab limit queries
    - Exclusion queries: verify returned `section_header` contains "Exclusion" and NOT "Inclusion"
    - Abstention queries: verify unrelated medical queries return `[]` or fall below similarity floor
    - Verify all returned `chunk_id`s exist in `trial_chunks` and no fabricated NCT IDs appear

---

### Guardrails & Non-Negotiables
- **No external reranker libraries:** Do NOT add `rank_bm25`, `sentence-transformers`, or Cohere. Postgres handles both vector and lexical retrieval.
- **No hardcoded embedding models:** Always use `settings.OPENAI_EMBEDDING_MODEL` via `embed_texts()`.
- **No concurrency on AsyncSession:** Never use `asyncio.gather` for queries on the same session.
- **Read-only retrieval:** `backend/app/retrieval/` must never write to the database.
- **Locked RRF_K:** Keep `RRF_K = 60` as spec'd; do not tune without a formal evaluation benchmark.

---

### Definition of Done for Phase 4
1. `uv run pytest` passes all offline tests (0 failures).
2. `uv run pytest -m integration` passes against live Supabase.
3. Manual chat smoke test yields streaming tokens citing real landmark NCT IDs from the 25-trial corpus.
4. `grep -r "NCT05794958" backend/` returns 0 results.
5. Zero DB connections held across SSE stream (D-4 property maintained).
6. File names reconciled across `todos.md` and `architecture.md`.

---

## Phase 5: Chat Shell Vertical Slice — Backend (in `backend/app/`)

> This phase builds the complete backend chat pipeline with a **stub retriever** replacing
> real pgvector search. Real retrieval is wired in Phase 4 (reverse order for velocity).
> Every endpoint requires a valid Supabase JWT — 403 on missing/invalid token.

- [x] **5.1 Shared Chat Schemas:**
  - [x] File: `backend/app/assistant/__init__.py`: Package marker
  - [x] File: `backend/app/assistant/schemas.py`:
    - `ChatRequest` — `thread_id: uuid | None`, `message: str`
    - `ThreadOut` — `id`, `title`, `created_at` (response model for thread endpoints)
    - `MessageOut` — `id`, `thread_id`, `role`, `content`, `created_at`
    - `ProtocolPassage` — stub chunk shape (`nct_id`, `section_header`, `chunk_text`) used by orchestrator

- [x] **5.2 Chat CRUD — Database Layer:**
  - [x] File: `backend/app/database/chats.py` (as specified in architecture `database/chats.py`):
    - `upsert_profile(session, user_id, email)` — INSERT … ON CONFLICT DO NOTHING so first-chat auto-creates the `profiles` row from JWT identity (required: `ChatThread.user_id` FK to `profiles.id`)
    - `create_thread(session, user_id, title) → ChatThread`
    - `list_threads(session, user_id) → list[ChatThread]` — ordered newest-first
    - `get_thread(session, thread_id, user_id) → ChatThread | None` — ownership-checked
    - `delete_thread(session, thread_id, user_id)` — raises 404 if not found, 403 if wrong owner
    - `list_messages(session, thread_id, user_id) → list[ChatMessage]` — oldest-first
    - `persist_turn(session, thread_id, user_content, assistant_content)` — writes user + assistant `ChatMessage` rows in one transaction after stream completes

- [x] **5.3 Streaming Chat Orchestrator:**
  *Audit fix: short-lived DB sessions (no DB hold during SSE stream); `BaseException` persist guard; 8k token history trim; graceful `3:` error frames.*
  - [x] File: `backend/app/chat/__init__.py`: Package marker
  - [x] File: `backend/app/chat/orchestrator.py`:
    - `stream_chat_turn(db, user, request) → AsyncGenerator[str, None]`
    1. Call `upsert_profile()` — ensures profiles row exists for JWT user
    2. Create or load `ChatThread` (create new if `thread_id=None`; ownership-check if UUID given)
    3. Call `_stub_retrieve(message)` → returns 1 hardcoded `ProtocolPassage` (replaced by `hybrid.retrieve()` in Phase 4, no other changes needed)
    4. Load last 10 messages from thread as conversation history
    5. Build OpenAI messages array: system prompt + history + user turn with stub passage as context
    6. Call `openai.AsyncOpenAI` (using `settings.effective_api_key` / `settings.effective_base_url`) with `stream=True`
    7. Yield each token delta as Vercel AI SDK data-stream frame: `0:"<token>"\n`
    8. After stream closes, call `persist_turn()` to write both messages to DB in one transaction
    9. Yield final frame: `d:{"finishReason":"stop"}\n`

- [x] **5.4 FastAPI Chat Endpoints:**
  *Audit fix: removed `db` session dependency from `chat_stream` route.*
  - [x] File: `backend/app/api/chat.py` — all routes require `get_current_user`:
    - `POST /api/chat/threads` → create thread → `ThreadOut` (201)
    - `GET /api/chat/threads` → list user's threads → `list[ThreadOut]`
    - `DELETE /api/chat/threads/{thread_id}` → delete (ownership-check) → 204
    - `GET /api/chat/threads/{thread_id}/messages` → history → `list[MessageOut]`
    - `POST /api/chat/stream` → `StreamingResponse(media_type="text/event-stream")` wrapping `stream_chat_turn()`
  - [x] File: `backend/app/api/router.py`:
    - Central API router registering all feature sub-routers under `/api` prefix
    - `GET /api/me`: Smoke-test endpoint returning `AuthenticatedUser` (proves end-to-end JWT chain)
    - [x] Register `chat_router` from `app.api.chat` under `/api`
  - [x] File: `backend/app/main.py`:
    - FastAPI app factory, CORS middleware, lifespan events, healthcheck route (`GET /health`)
    - Mounts `api_router` from `app.api.router`

- [x] **5.5 PydanticAI Agent & Grounding (Post-retrieval — Phase 5 proper):**
  - [x] File: `backend/app/assistant/deps.py`:
    - `OncologyAgentDeps` holding user identity, thread ID, retrieved protocol passages, and settings
  - [x] File: `backend/app/assistant/prompts.py`:
    - Oncology clinical system prompt with strict negative constraints
    - Explicit instruction: *"If the protocol does not state a criterion, explicitly state: 'The protocol does not state [X].'"*
    - Mandatory bracketed citation formatting: `[NCTxxxxxxx, Section Title: Criterion #]`
    - Context formatting utilities (`format_protocol_context`, `build_chat_messages`)
  - [x] File: `backend/app/assistant/agent.py`:
    - PydanticAI agent configuration with OpenRouter / OpenAI compatibility and dynamic context injection
  - [x] File: `backend/app/grounding/validator.py`:
    - `GroundingValidator` parses bracket citations (`[NCT..., Section]`), matches them against retrieved candidate passages, deduplicates, and extracts verbatim quotes
    - Strips/flags ungrounded citations to guarantee zero hallucination
    - Persists verified citations to `message_citations` table in short-lived `post_session` (maintaining D-3 / D-4)
    - Eager-loads citations with `selectinload` in `list_messages` for instant coordinator inspection

- [x] **5.6 Protocol & Trial Endpoints (for Phase 6.6 Trial Catalog):**
  - [x] File: `backend/app/database/trials.py`:
    - `list_trials()` with category/status filters, ordered by category and NCT ID
    - `get_trial()` and `get_trial_with_chunks()` with sorted chunk index
  - [x] File: `backend/app/assistant/schemas.py`:
    - Added `TrialSummary`, `TrialChunkOut`, `TrialDetail`, `CitationOut`, `MessageCitationCreate` matching frontend `api.ts` contracts
  - [x] File: `backend/app/api/trials.py`:
    - `GET /api/trials` → list active trials with phase/cancer type filters → `list[TrialSummary]`
    - `GET /api/trials/{nct_id}` → full trial detail with all criteria and eligibility rules → `TrialDetail`
  - [x] File: `backend/app/api/router.py`:
    - Mounted `trials_router` under `/api`


---

## Phase 6: Frontend Clinical UI (in `frontend/`)

- [x] **6.1 Scaffolding & Build Tooling:**
  *Audit fix: removed unused `@ai-sdk/react` & `ai` packages (13 packages).*
  - [x] Initialize Vite + React 19 Single Page Application with TypeScript (`pnpm create vite . --template react-ts`)
  - [x] File: `frontend/package.json`:
    - Dependencies: `@supabase/supabase-js`, `react-router-dom`, `lucide-react`, `clsx`, `tailwind-merge`, `@base-ui/react`
    - Dev dependencies: `tailwindcss` (v4), `@tailwindcss/vite`
  - [x] File: `frontend/vite.config.ts`: Vite build configuration with `@tailwindcss/vite` and `@/*` alias
  - [x] File: `frontend/src/index.css`: Tailwind CSS v4 directives and Nova theme tokens
  - [x] Initialize shadcn/ui with Base UI Nova preset (`components.json`, `src/lib/utils.ts`, `src/components/ui/button.tsx`)


- [x] **6.2 Environment, Auth Client & Login Page:**
  *Audit fix: aligned `TrialSummary`/`TrialDetail` in `api.ts` to DB schema; fixed `.gitignore` to track `frontend/src/lib/`.*
  - [x] File: `frontend/src/lib/env.ts`: Single source of truth for frontend environment variables (`VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)
  - [x] File: `frontend/src/lib/supabase.ts`: Supabase browser client (singleton, `persistSession: true`, `autoRefreshToken: true`)
  - [x] File: `frontend/src/lib/api.ts`: Fetch wrapper that automatically attaches the Supabase session JWT to outbound requests; typed `api.me()`, `api.trials.*`, `api.chat.*` helpers
  - [x] File: `frontend/src/context/AuthContext.tsx`: Institutional email auth session provider
  - [x] File: `frontend/src/pages/Login.tsx`: Clinical login screen with email + password (`signInWithPassword`)
  - [x] File: `frontend/src/components/ProtectedRoute.tsx`: Redirect unauthenticated users to `/login`
  - [x] File: `frontend/src/App.tsx`: React Router wired with `AuthProvider`, `/login` route, and protected `/` route
  - [x] File: `frontend/src/pages/Dashboard.tsx`: Auth smoke-test screen — calls `GET /api/me` and displays backend-verified identity

- [x] **6.4 Chat Shell — Frontend:**
  *Audit fix: clarified native SSE `ReadableStream` parser in `useChatStream.ts` instead of `useChat`.*
  - [x] File: `frontend/src/lib/api.ts` **(extend existing)**:
    - Add `api.chat.createThread()` → `ThreadOut`
    - Add `api.chat.deleteThread(id)` → `void`
    - Export `ThreadOut` and `MessageOut` TypeScript interfaces matching backend schemas
  - [x] File: `frontend/src/App.tsx` **(modify existing)**:
    - Add `/chat` and `/chat/:threadId` routes (both `ProtectedRoute`)
    - Redirect `/` → `/chat`
    - Remove old `Dashboard` import
  - [x] File: `frontend/src/pages/ChatPage.tsx`: Top-level page for `/chat/:threadId?` — split layout (ThreadSidebar left, ChatContainer right)
  - [x] File: `frontend/src/components/chat/ThreadSidebar.tsx`:
    - Load `api.chat.threads()` on mount
    - "New chat" button → `api.chat.createThread()` → navigate to `/chat/<new-id>`
    - Thread list: each item navigates to `/chat/<id>`, highlights active thread
    - Delete (×) button per thread
    - User email + Sign out at bottom
  - [x] File: `frontend/src/components/chat/ChatContainer.tsx`: Streaming conversation view with Vercel AI SDK data-stream protocol and `Authorization` header injection
  - [x] File: `frontend/src/components/chat/ChatMessage.tsx`: User (right-aligned) and assistant (left-aligned) message bubbles with formatted clinical citation pills
  - [x] File: `frontend/src/components/chat/ChatInput.tsx`: Auto-growing textarea, Enter submits / Shift+Enter newline, disabled+spinner when streaming, quick-prompt chips

- [x] **6.5 Interactive Evidence Inspection & Citation Popovers:**
  - [x] File: `frontend/src/components/citations/CitationPill.tsx`: Clickable badge (`[NCT07659782, Exclusion #4]`) that toggles protocol popover
  - [x] File: `frontend/src/components/citations/CitationPopover.tsx`: Popover drawer displaying verbatim quote, NCT ID, section header, and protocol amendment date
  - [x] File: `frontend/src/components/chat/MarkdownContent.tsx`: Markdown parser and renderer for structured oncology responses (bold, bullet/numbered lists, headings, and seamless `CitationPill` embedding without raw asterisks)

- [x] **6.6 Protocol Viewer & Trial Catalog:**
  - [x] File: `frontend/src/components/trials/TrialCard.tsx`: Trial summary card showing disease category, sponsor, phase, and status
  - [x] File: `frontend/src/components/trials/TrialList.tsx`: Filterable catalog of the 25 landmark trials with dynamic category pills, database snake_case matching, and full-text search
  - [x] File: `frontend/src/components/trials/TrialDetailDrawer.tsx`: Full protocol viewer drawer for cross-referencing criteria and sequential chunk reading
  - [x] File: `frontend/src/pages/TrialsPage.tsx`: Dedicated trial catalog page accessible via sidebar nav and `/trials` route
  - [x] File: `frontend/src/context/ThemeContext.tsx` & `frontend/src/index.css`: Dark/Light theme system featuring Clinical Dusk dark mode and ChatGPT-inspired clean white/gray light mode with sidebar toggle

---

## Phase 7: Benchmark Evaluation & Deployment

- [x] **7.1 Clinical Benchmark Verification:**
  *Pilot gate verified: 10/10 coordinator screening questions grounded against live Supabase pgvector/FTS + GPT-4o; 100% citation grounding (0 hallucinated criteria); negative refusal verified on protocol silence (Q10 on NCT02277548) and adversarial off-corpus set.*
  - [x] File: `backend/tests/test_clinical_benchmarks.py`:
    - [x] Run the 10 real-world coordinator screening benchmark questions from the project brief
    - [x] Verify 100% citation grounding (0 hallucinated criteria)
    - [x] Verify negative refusal behavior on protocol silence queries
    - [x] Verify 5 adversarial off-corpus refusal queries (pediatric GBM finding C3 guard, pancreatic, Alzheimer's, France, prompt injection)
    - [x] Verify database test thread cleanup (0 residue left behind)
  - [x] File: `backend/tests/test_pilot_readiness.py`:
    - [x] Stress & adversarial suite (53 offline + live integration tests) covering prompt injection inside protocol text, malformed citations, sanitizer idempotence, multi-turn grounding, client disconnect persistence (D-3), and cross-tenant isolation
- [x] **7.2 Pre-Deployment Security Hardening:**
  *All findings from the security audit resolved before going live on Render.*

  **🔴 Critical**

  - [x] **S1 — Restrict CORS Methods & Headers** *(File: `backend/app/main.py`)*:
    - Replace `allow_methods=["*"]` with `["GET", "POST", "DELETE", "OPTIONS"]`
    - Replace `allow_headers=["*"]` with `["Authorization", "Content-Type"]`
    - Risk: wildcard methods + `allow_credentials=True` widens the cross-origin attack surface beyond what the API actually uses

  - [x] **S2 — Lock Down Swagger/Redoc Exposure** *(File: `backend/app/main.py`)*:
    - Change `docs_url`/`redoc_url` to expose only when `settings.DEBUG is True` (not environment-gated)
    - Current logic exposes docs for any `ENVIRONMENT` value that isn't exactly `"production"` — a typo like `"prod"` or `"Production"` leaks the full API schema publicly
    - ```diff
      - docs_url="/docs" if settings.ENVIRONMENT != "production" or settings.DEBUG else None,
      + docs_url="/docs" if settings.DEBUG else None,
      ```

  - [x] **S3 — Strip Internal Config from Health Endpoint** *(File: `backend/app/main.py`)*:
    - Remove `environment`, `chat_model`, and `embedding_model` from the `/health` response
    - Keep only `status` and `app_name` — load balancers need a 200, not your AI provider and model routing details
    - Risk: anonymous visitors learn your LLM provider, model names, and environment mode

  **🟠 High**

  - [x] **S4 — Add Rate Limiting to LLM-Backed Endpoints**:
    - Created `backend/app/middleware/rate_limit.py` with a sliding-window per-user limiter
    - Cap `/api/chat/stream` at ~30 requests per 60s per user to prevent OpenAI/OpenRouter credit exhaustion
    - Registered as middleware in `main.py` after `CORSMiddleware`

  - [x] **S5 — Prevent Debug/Reload in Production** *(File: `backend/app/main.py`)*:
    - Changed `reload=settings.DEBUG or settings.ENVIRONMENT == "development"` to `reload=settings.ENVIRONMENT == "development" and settings.DEBUG`
    - Ensure Render start command uses: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (never `python -m`)

  **🟡 Medium**

  - [x] **S6 — Add Security Headers Middleware**:
    - Created `backend/app/middleware/security_headers.py` setting `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`
    - Registered in `main.py` before `CORSMiddleware`

  - [x] **S7 — Cap Chat Message Input Length** *(File: `backend/app/assistant/schemas.py`)*:
    - Added `max_length=4000` to `ChatRequest.message` field via `pydantic.Field`
    - Prevents oversized prompts from exhausting embedding tokens, LLM context, and database storage

  - [x] **S8 — Sanitize Startup Logging** *(File: `backend/app/main.py`)*:
    - Replaced `print()` calls in lifespan with `logging.getLogger(__name__).info()`
    - No longer logs the full `ALLOWED_ORIGINS` list or model names — logs only origin count and environment

- [ ] **7.3 Render Deployment — Infrastructure as Code & Container Assets:**
  - [ ] **7.3.1 Render Blueprint (`render.yaml`)**:
    - Infrastructure-as-code specification in repository root orchestrating both services in one click
    - Define Backend Web Service (`scri-copilot-backend`):
      - Runtime: `docker` or `python` (Python 3.12)
      - Root directory: `backend`
      - Plan: `free` (512 MB RAM / 0.1 vCPU)
      - Build command: `pip install --upgrade pip && pip install uv && uv sync --no-dev`
      - Start command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
      - Health check path: `/health`
    - Define Frontend Static Site (`scri-copilot-frontend`):
      - Runtime: `static`
      - Root directory: `frontend`
      - Plan: `free` (Global edge CDN, 0s spin-down)
      - Build command: `npm install -g pnpm && pnpm install && pnpm build`
      - Publish directory: `dist`
      - SPA rewrite routes: `/*` -> `/index.html` (prevents 404 on direct navigation to `/chat` or `/trials`)
  - [ ] **7.3.2 Backend Containerization (`backend/Dockerfile`)**:
    - Multi-stage or slim Python 3.12 image (`python:3.12-slim`)
    - Install `uv` binary via `ghcr.io/astral-sh/uv:latest`
    - Copy `pyproject.toml` and `uv.lock` for deterministic, frozen dependency installation
    - Ensure dynamic `$PORT` binding so Uvicorn listens on Render's assigned port (`0.0.0.0:$PORT`)
  - [ ] **7.3.3 Frontend Static Build Verification (`frontend/`)**:
    - Verify `pnpm build` creates clean production bundle in `frontend/dist/` without TypeScript or lint warnings
    - Ensure SPA client-side routing fallback (`/*` -> `/index.html`) is active in Render

- [ ] **7.4 Render Environment Configuration & Secrets Management:**
  - [ ] **7.4.1 Backend Service Environment Variables**:
    - `PYTHON_VERSION = 3.12.8`
    - `ENVIRONMENT = production`
    - `DEBUG = false` (locks down Swagger `/docs` and detailed stack traces)
    - `HOST = 0.0.0.0`
    - `SUPABASE_URL = <project-url>`
    - `SUPABASE_ANON_KEY = <anon-key>`
    - `SUPABASE_SERVICE_ROLE_KEY = <service-role-key>` (secret, server-side only)
    - `DATABASE_URL = <direct-postgres-connection-port-5432>` (required for session-level vector queries)
    - `OPENAI_API_KEY = <openai-or-openrouter-key>`
    - `OPENAI_CHAT_MODEL = gpt-4o`
    - `OPENAI_EMBEDDING_MODEL = text-embedding-3-small`
    - `ALLOWED_ORIGINS = https://scri-copilot.onrender.com,http://localhost:5173`
  - [ ] **7.4.2 Frontend Static Site Build-Time Environment Variables**:
    - `VITE_API_BASE_URL = https://scri-copilot-backend.onrender.com` (Render Web Service public URL)
    - `VITE_SUPABASE_URL = <project-url>`
    - `VITE_SUPABASE_ANON_KEY = <anon-key>`
    - *Note:* Must be configured in Render before running the build step so Vite statically injects them into the bundle.

- [ ] **7.5 Post-Deployment Verification, CORS Handshake & Health:**
  - [ ] **7.5.1 Backend Health & Smoke Testing**:
    - Query `GET https://scri-copilot-backend.onrender.com/health` to confirm HTTP 200 `{"status": "healthy", "app_name": "SCRI Oncology Copilot"}`
    - Verify `/docs` returns HTTP 404 (Swagger disabled in production)
    - Verify database connectivity to Supabase and pgvector index
  - [ ] **7.5.2 Cross-Origin Handshake (CORS)**:
    - Update backend `ALLOWED_ORIGINS` with the finalized Render frontend domain
    - Verify pre-flight `OPTIONS` requests pass with `Access-Control-Allow-Origin`
  - [ ] **7.5.3 End-to-End Clinical Screening Validation**:
    - Test coordinator login at `https://scri-copilot.onrender.com/login`
    - Browse 25 landmark trials in `/trials` catalog
    - Ask benchmark question (e.g. brain metastases in NSCLC) and verify SSE token streaming (`text/event-stream`)
    - Inspect interactive citation pills and drawer popovers
    - Verify off-corpus refusal (e.g. pediatric glioblastoma) triggers deterministic C3 guard
  - [ ] **7.5.4 Keep-Alive / Cold-Start Mitigation (Free Tier)**:
    - Set up an automated 10-minute HTTP ping on [cron-job.org](https://cron-job.org) or [uptimerobot.com](https://uptimerobot.com) targeting `https://scri-copilot-backend.onrender.com/health`
    - Keeps the 512 MB container awake during clinical screening hours, eliminating the 45-50s free tier spin-up delay

---

## Phase 8: High-Value RAG Engineering & Retrieval Benchmarking (Scoped Production-Grade Capabilities)

> **Scope Rationale (Prototype vs. Enterprise):** Since this is an AI showcase and portfolio project rather than a live hospital-integrated EHR system, enterprise HIPAA and operational overhead is safely bypassed (no Presidio PHI middleware, no 6-year immutable audit log tables, no 4-tier RBAC, no Redis/PgBouncer connection clustering, and no daily ClinicalTrials.gov scraping daemons).
> Instead, all effort focuses on **core RAG intelligence, rigorous retrieval benchmarking, and clinical UI trust**.

- [x] **8.1 Multi-Turn Context & Query Augmentation (Context Retention):**
  - **Problem:** When coordinators ask follow-up questions (e.g., Turn 1: *"Does NCT05794958 allow brain metastases?"* ➔ Turn 2: *"What about prior steroid use for that same patient?"*), naive RAG loses Turn 1's trial context because Turn 2's retrieval query is executed purely on the raw text `"What about prior steroid use for that same patient?"`.
  - [x] File: `backend/app/chat/orchestrator.py`:
    - Implement `build_retrieval_query(message: str, history: list[ChatMessage]) -> str`:
      - Inspect preceding assistant turn for verified citations (`nct_id` and `section_header`).
      - Prepend active NCT ID(s) and clinical anchors to the incoming user message prior to calling `retrieve_protocols()`.
      - Prevents evidence starvation on follow-up turns while keeping retrieval focused on the active trial.
  - [x] File: `backend/tests/test_multi_turn.py`:
    - Unit & integration tests verifying:
      - Standalone questions retain raw query text without extraneous prefixing.
      - Follow-up questions without explicit NCT mentions successfully anchor to the previously cited protocol.
      - Cross-turn grounding validation succeeds without hallucinated citations.

- [x] **8.2 Industry-Standard Retrieval & Grounding Evaluation Suite:**
  - **Goal:** Benchmark the hybrid retrieval pipeline (pgvector + FTS + RRF) against industry-standard Information Retrieval (IR) and RAG metrics.
  - [x] **Benchmark Metrics Standard:**
    - **Recall@1 (Top-1 Accuracy):** Proportion of queries where the exact target protocol chunk is ranked at position #1. Target: $\ge 60\%$. (Measured: **95.5%**)
    - **Recall@3:** Proportion of queries where the target chunk appears in the top 3 retrieved results. Target: $\ge 80\%$. (Measured: **100.0%**)
    - **Recall@5 / Recall@10 (Retrieval Ceiling):** Proportion of queries where the target chunk appears anywhere in the top 5 / 10 passages injected into the LLM context. Target: $\ge 95\%$. (Measured: **100.0%**)
    - **MRR (Mean Reciprocal Rank):** Average reciprocal rank ($\frac{1}{\text{rank}}$) of the first relevant passage. Target: $\ge 0.70$. (Measured: **0.970**)
    - **Grounding / Citation Precision:** 100% of LLM-generated citations must match a retrieved chunk ID with an exact verbatim quote (0 tolerance for fabricated criteria).
    - **Negative Refusal Precision & Recall:** 100% refusal rate on off-corpus queries and protocol silence questions ("protocol does not state [X]"). (Measured: **100.0%**)
  - [x] File: `backend/eval/golden_dataset.json`:
    - Curated golden evaluation set of 25 clinical queries across the 5 landmark cancer types (washout periods, biomarker exclusions, platelet thresholds, prior therapies) plus 3 negative refusal controls.
  - [x] File: `backend/eval/evaluate_retrieval.py`:
    - CLI runner and automated eval script running against test DB.
    - Computes and prints a formatted terminal scorecard:
      - `Recall@1`, `Recall@3`, `Recall@5`, `Recall@10`
      - `Mean Reciprocal Rank (MRR)`
      - `Citation Precision` & `Refusal Accuracy`
      - Latency (P50 and P95 retrieval time)
    - Exports machine-readable audit report to `backend/eval/reports/latest_report.json` and human-readable executive summary to `docs/eval-report.md`.
  - [x] Integrate into CI (`backend/tests/test_retrieval_benchmarks.py`):
    - Automated assertion test verifying that `latest_report.json` meets all SLA targets and providing a live `@pytest.mark.integration` runner.

- [x] **8.3 Clinical UI Trust & Polish (Presentation Layer):**
  - [x] **Persistent Clinical Disclaimer Footer**:
    - File: `frontend/src/components/chat/ChatContainer.tsx` (and `frontend/src/components/chat/ChatInput.tsx`):
    - Prominent clinical disclaimer banner:
      > *"SCRI Oncology Copilot is an AI screening assistant, not a clinical decision system. All eligibility determinations must be confirmed against the source protocol before enrollment."*
  - [x] **Enhanced Citation Previews & Drawer Quick-Inspection**:
    - Files: `frontend/src/components/citations/CitationPopover.tsx`, `frontend/src/components/citations/CitationDrawer.tsx`, `frontend/src/components/trials/TrialDetailDrawer.tsx`:
    - Added quick-jump action: clicking "View in Protocol" opens the `TrialDetailDrawer` auto-scrolled and highlighted with a glowing teal accent to that exact cited chunk.
  - [x] **Lightweight User Feedback Mechanism**:
    - Files: `frontend/src/components/chat/ChatMessage.tsx`, `backend/app/api/chat.py`, `backend/app/database/chats.py`:
    - Thumbs up / Thumbs down reaction buttons on assistant messages.
    - Persists feedback state (`helpful` / `unhelpful`) to chat message `metadata_json` with user tenancy verification for tracking answer quality.


