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
| Hosting | Railway (backend API + frontend SPA) |
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
