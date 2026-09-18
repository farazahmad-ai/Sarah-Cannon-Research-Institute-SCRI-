# Agent Instructions — Sarah Cannon Research Institute (SCRI) Copilot

This document is the authoritative source of truth for any AI coding agent (Claude Code, Antigravity, Cursor, Codex, etc.) operating within the `Sarah Cannon Research Institute (SCRI)` workspace. Read this entire document before reading or editing code.

---

## 1. Project Mission & Domain Context

You are building **SCRI Oncology Copilot** (an intelligent clinical trial protocol assistant) for **Sarah Cannon Research Institute (SCRI)**. 

### The User Persona:
- **Primary Users:** Clinical Research Coordinators (CRCs), Molecular Tumor Board (MTB) navigators, and Principal Investigators across SCRI's network of 250+ community cancer clinics.
- **The Core Problem:** Coordinators spend 15–20 hours every week manually cross-referencing 100+ page clinical trial protocols to screen cancer patients against complex inclusion/exclusion criteria (prior therapy washouts, biomarker thresholds, organ function limits, brain metastases stability).
- **The Core Value:** The copilot provides instant, grounded answers to plain-English questions across active trial protocols, cutting intake time by 75% without compromising clinical safety.

---

## 2. The Golden Rules (Non-Negotiable)

1. **Zero Hallucination / Absolute Grounding:** In oncology, a fabricated eligibility criterion or hallucinated lab threshold is dangerous. If a protocol does not explicitly mention a criterion, the model must explicitly state: *"The protocol does not state [X]."* Never guess, extrapolate, or generalize from other medical literature.
2. **Mandatory Verbatim Citations:** Every single factual statement must be backed by a citation to the specific **NCT ID** and protocol section (e.g., `[NCT05794958, Eligibility: Exclusion Criterion #4]`). The underlying passage must be viewable in one click.
3. **No Protected Health Information (PHI):** The system operates strictly on **unclassified clinical trial protocols** (public domain documents from ClinicalTrials.gov), never on patient charts, medical records, or EHR entries.
4. **Stack is Locked:** The technology stack is fixed. Do not propose, install, or introduce alternative frameworks or databases without explicit user direction.

---

## 3. Technology Stack

The declared enterprise stack for this deployment:

| Layer | Technology | Role & Notes |
| :--- | :--- | :--- |
| **Backend** | Python 3.12+ / FastAPI / Uvicorn | Request validation, orchestration, streaming endpoints |
| **Agent / Orchestration** | PydanticAI | Typed dependencies, typed agent outputs, citation enforcement |
| **Database** | Supabase Postgres | Persistent storage for users, chats, trials, and chunks |
| **Search & Retrieval** | `pgvector` + Postgres Full-Text Search | Hybrid retrieval with Reciprocal Rank Fusion (RRF) |
| **Migrations** | SQLAlchemy + Alembic | Declarative models and tracked migrations from backend |
| **Embeddings & LLM** | OpenAI API | `text-embedding-3-small` for chunks; `gpt-4o` for grounded answers |
| **Auth** | Supabase Auth | Institutional email sessions (no third-party OAuth) |
| **Frontend** | React 18+ / Vite / TypeScript (strict) | Single Page Application (SPA), no SSR / Next.js |
| **Styling & UI** | Tailwind CSS + shadcn/ui | Clean, accessible clinical UI primitives |
| **Client Streaming** | Vercel AI SDK React primitives | Streaming response state and message history |
| **Hosting** | Railway | Two containerized services (Backend API + Frontend SPA) |

---

## 4. Repository Layout

```text
Sarah Cannon Research Institute (SCRI)/
├── AGENTS.md                          # Source of truth for agents (this file)
├── README.md                          # Quickstart, local setup, prerequisites
├── .gitignore                         # Git exclusion rules
├── data/                              # Data ingestion pipeline
│   ├── download.py                    # ClinicalTrials.gov REST API v2 downloader
│   └── downloads/                     # Local protocol JSONs & manifest (gitignored)
├── docs/                              # Technical architecture and guides
│   ├── architecture.md                # System diagrams, data flow, and schemas
│   ├── project-brief.md               # Real-world clinical case study & requirements
│   ├── guide.md                       # Comprehensive setup & deployment guide
│   └── todos.md                       # Step-by-step implementation checklist
├── backend/                           # FastAPI service
│   ├── alembic/                       # Database migrations
│   ├── app/
│   │   ├── api/                       # HTTP route handlers (chat, ingest, auth)
│   │   ├── assistant/                 # PydanticAI agent, prompts, tool definitions
│   │   ├── auth/                      # Supabase JWT token verification
│   │   ├── config.py                  # Pydantic settings (single source of truth for env)
│   │   ├── database/                  # SQLAlchemy models & Supabase DB helpers
│   │   ├── grounding/                 # Citation validator & grounding enforcement
│   │   └── retrieval/                 # pgvector + FTS hybrid search & RRF fusion
│   ├── pyproject.toml
│   └── AGENTS.md                      # Backend-specific agent guidelines
└── frontend/                          # Vite + React SPA
    ├── src/
    │   ├── components/                # UI components (chat, citation popover, trial viewer)
    │   ├── lib/                       # API client, auth helpers, env configuration
    │   ├── pages/                     # Route-level screens (Chat, History, Trial Library)
    │   ├── App.tsx                    # React Router configuration
    │   └── main.tsx                   # App entrypoint
    ├── package.json
    └── AGENTS.md                      # Frontend-specific agent guidelines
```

---

## 5. Agent Workflow & Execution Rules

When implementing or editing code within this repository, adhere strictly to these practices:

### A. Configuration & Environment Variables
- **Backend:** `backend/app/config.py` is the single source of truth. Never call `os.getenv()` or `load_dotenv()` directly in application code.
- **Frontend:** `frontend/src/lib/env.ts` is the single source of truth. Never read `import.meta.env` or `process.env` directly in components.
- **Fail Fast:** If an essential configuration key (e.g., `OPENAI_API_KEY`, `SUPABASE_URL`) is missing on startup, crash immediately with an informative error message.

### B. Dependency Discipline
- **Default:** Write it yourself. Do not install utility libraries for trivial functions (e.g., date formatting, string casing, array manipulation).
- **Backend:** Prefer standard library modules (`pathlib`, `datetime`, `dataclasses`, `asyncio`, `json`, `urllib`).
- **Frontend:** Use native browser APIs and TS/JS built-ins. **pnpm only** (`minimum-release-age=10080`). Do not install `axios`, `lodash`, or `moment`. Use shadcn for UI primitives.

### C. Backend Architecture Patterns
- **Async by Default:** All FastAPI route handlers, database operations, and HTTP network requests must use `async def` and non-blocking I/O.
- **Boundary Validation Only:** Validate inputs at HTTP boundaries using Pydantic schemas. Trust internal calls between internal modules.
- **Hybrid Retrieval Flow:**
  1. Query `pgvector` for semantic similarity using cosine distance.
  2. Query Postgres full-text search (`to_tsquery`) for exact medical keyword matching (e.g., *EGFR Exon 20*, *DLT*, *ANC*).
  3. Fuse results in memory using Reciprocal Rank Fusion (RRF).
  4. Pass fused chunks with `nct_id`, section header, and paragraph text to PydanticAI.

### D. Grounding & Citation Validation
- Prior to streaming or finalizing an answer, verify that every cited bracket reference matches a chunk ID that was retrieved in that turn.
- Strip or correct ungrounded citations before delivering the response to the user.

---

## 6. Code Style Conventions

- **Small, Focused Functions:** A 15-to-25 line function with descriptive naming is preferred over nested abstractions.
- **No Premature Abstraction:** Write three concrete lines before attempting to extract a generic helper.
- **Explain "Why", Not "What":** Code comments must explain clinical or architectural intent that is non-obvious. Never write comments that merely rephrase the syntax.
