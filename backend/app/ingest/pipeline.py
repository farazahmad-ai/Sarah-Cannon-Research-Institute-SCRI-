"""Ingestion pipeline CLI for SCRI Oncology Copilot.

Reads the manifest.json produced by data/download.py, chunks all 25 landmark
oncology trials into section-aware protocol passages, generates dense embeddings,
and upserts everything into Supabase Postgres via SQLAlchemy.

Usage:
    # Stage 1: Inspect chunks for 1 trial -- no API calls, no DB writes
    uv run python -m app.ingest.pipeline --dry-run --limit 1

    # Stage 2: Full end-to-end for 1 trial (embedding + DB)
    uv run python -m app.ingest.pipeline --limit 1

    # Stage 3: One trial per disease category (5 trials, spot-check variation)
    uv run python -m app.ingest.pipeline --one-per-category

    # Stage 4: Full run -- all 25 trials
    uv run python -m app.ingest.pipeline

    # Single trial by NCT ID (useful for re-ingesting one updated trial)
    uv run python -m app.ingest.pipeline --nct-id NCT06498635
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Pipeline must be run from the backend/ directory so relative imports resolve
# Path resolution: backend/app/ingest/pipeline.py -> backend/data/downloads/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_DOWNLOADS_DIR = _BACKEND_DIR.parent / "data" / "downloads"
_MANIFEST_PATH = _DOWNLOADS_DIR / "manifest.json"

from app.database.models import ClinicalTrial, TrialChunk
from app.database.session import async_session_factory
from app.ingest.chunker import ChunkPayload, ParsedTrial, chunk_protocol, load_trial_json
from app.retrieval.embeddings import embed_texts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SCRI protocol ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chunks to stdout. No embedding API calls, no DB writes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N trials from the manifest.",
    )
    parser.add_argument(
        "--nct-id",
        type=str,
        default=None,
        metavar="NCT_ID",
        help="Process a single trial by NCT ID (e.g. NCT06498635).",
    )
    parser.add_argument(
        "--one-per-category",
        action="store_true",
        help="Process the first trial from each disease category (5 trials total).",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Write chunks to DB but skip embedding API calls (schema validation mode).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Allow --skip-embed to overwrite trials that already have embeddings. "
            "Without this flag, --skip-embed refuses to run against an already-embedded "
            "trial to prevent silent destruction of the vector index."
        ),
    )
    return parser.parse_args()


def _load_manifest() -> list[dict]:
    """Load and return the studies list from manifest.json."""
    if not _MANIFEST_PATH.exists():
        logger.error("Manifest not found at %s", _MANIFEST_PATH)
        logger.error("Run: uv run python data/download.py  (from the project root)")
        sys.exit(1)
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return manifest.get("studies", [])


def _select_studies(studies: list[dict], args: argparse.Namespace) -> list[dict]:
    """Filter the manifest study list based on CLI flags."""
    if args.nct_id:
        matched = [s for s in studies if s["nct_id"].upper() == args.nct_id.upper()]
        if not matched:
            logger.error("NCT ID %s not found in manifest.", args.nct_id)
            sys.exit(1)
        return matched

    if args.one_per_category:
        seen_categories: set[str] = set()
        selected: list[dict] = []
        for study in studies:
            cat = study.get("category", "")
            if cat not in seen_categories:
                seen_categories.add(cat)
                selected.append(study)
        return selected

    if args.limit:
        return studies[: args.limit]

    return studies


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------

def _print_dry_run(trial: ParsedTrial, chunks: list[ChunkPayload]) -> None:
    """Pretty-print chunk details to stdout for visual inspection."""
    separator = "=" * 70

    def safe(text: str) -> str:
        # Encode to ASCII with replacement so Windows CP1252 terminals don't crash
        # on Unicode medical symbols (>=, <=, etc.) from the protocol JSON.
        return text.encode("ascii", errors="replace").decode("ascii")

    print(f"\n{separator}")
    print(safe(f"TRIAL: {trial.nct_id}  |  {trial.brief_title[:60]}..."))
    print(f"Category: {trial.category}  |  Phases: {trial.phases}  |  Status: {trial.status}")
    print(f"Total chunks: {len(chunks)}")
    print(separator)

    for chunk in chunks:
        print(f"\n[{chunk.chunk_index:02d}] {chunk.section_type}  --  {chunk.section_header}")
        print(f"     Tokens: ~{chunk.token_count}")
        # Show first 200 chars of the chunk text for visual spot-check
        preview = chunk.chunk_text[:200].replace("\n", " ")
        print(safe(f"     Preview: {preview}{'...' if len(chunk.chunk_text) > 200 else ''}"))


# ---------------------------------------------------------------------------
# Database upsert
# ---------------------------------------------------------------------------

async def _upsert_trial(session, trial: ParsedTrial) -> None:
    """Upsert a ClinicalTrial row. ON CONFLICT updates existing rows."""
    trial_data = {
        "nct_id": trial.nct_id,
        "category": trial.category,
        "brief_title": trial.brief_title,
        "official_title": trial.official_title or None,
        "organization": trial.organization or None,
        "status": trial.status,
        "last_update_posted_date": trial.last_update_posted_date,
        "start_date": trial.start_date,
        "primary_completion_date": trial.primary_completion_date,
        "phases": trial.phases or None,
        "conditions": trial.conditions or None,
        "arms": trial.arms or None,
        "primary_outcomes": trial.primary_outcomes or None,
        "source_url": trial.source_url or None,
    }
    stmt = pg_insert(ClinicalTrial).values(**trial_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["nct_id"],
        set_={k: v for k, v in trial_data.items() if k != "nct_id"},
    )
    await session.execute(stmt)


async def _replace_chunks(
    session,
    nct_id: str,
    chunks: list[ChunkPayload],
    vectors: list[list[float]] | None,
) -> None:
    """Delete existing chunks for this trial then bulk-insert fresh ones.

    Using delete + insert (rather than per-row upsert) is simpler and correct:
    chunk_index values may shift if the chunker logic changes, so a clean
    replacement guarantees no stale criteria remain in the index.
    """
    await session.execute(
        delete(TrialChunk).where(TrialChunk.nct_id == nct_id)
    )

    chunk_rows: list[TrialChunk] = []
    for i, chunk in enumerate(chunks):
        embedding = vectors[i] if vectors else None
        chunk_rows.append(TrialChunk(
            nct_id=chunk.nct_id,
            chunk_index=chunk.chunk_index,
            section_type=chunk.section_type,
            section_header=chunk.section_header,
            chunk_text=chunk.chunk_text,
            embedding=embedding,
            token_count=chunk.token_count,
            metadata_json=chunk.metadata_json,
        ))

    session.add_all(chunk_rows)


# ---------------------------------------------------------------------------
# Per-trial pipeline
# ---------------------------------------------------------------------------

async def _process_trial(study: dict, args: argparse.Namespace) -> dict:
    """Run the full ingestion pipeline for one trial entry from the manifest.

    Returns a summary dict for the final report.
    """
    nct_id = study["nct_id"]
    category = study["category"]
    json_path = _DOWNLOADS_DIR / study["local_json_path"]

    if not json_path.exists():
        logger.warning("JSON file not found for %s at %s -- skipping", nct_id, json_path)
        return {"nct_id": nct_id, "status": "skipped", "chunks": 0}

    # Step 1: Parse JSON into ParsedTrial
    trial = load_trial_json(json_path)
    trial.category = category  # inject category from manifest

    # Step 2: Chunk the protocol
    chunks = chunk_protocol(trial)

    if args.dry_run:
        _print_dry_run(trial, chunks)
        return {"nct_id": nct_id, "status": "dry-run", "chunks": len(chunks)}

    # Step 3: Generate embeddings (unless --skip-embed)
    #
    # Safety guard (D-5): --skip-embed deletes existing chunks and re-inserts them
    # with embedding=NULL, which silently destroys the vector index for this trial.
    # Refuse if the trial already has non-null embeddings, unless --force is set.
    if args.skip_embed and not args.force:
        async with async_session_factory() as guard_session:
            existing_count: int = await guard_session.scalar(
                select(func.count()).where(
                    TrialChunk.nct_id == nct_id,
                    TrialChunk.embedding.is_not(None),
                )
            ) or 0
        if existing_count > 0:
            logger.error(
                "%s  --skip-embed refused: %d existing embedding(s) would be destroyed. "
                "Pass --force to override.",
                nct_id,
                existing_count,
            )
            return {"nct_id": nct_id, "status": "refused", "chunks": 0}

    vectors: list[list[float]] | None = None
    if not args.skip_embed:
        logger.info("%s  Generating embeddings for %d chunks...", nct_id, len(chunks))
        embed_inputs = [chunk.embed_text for chunk in chunks]
        vectors = await embed_texts(embed_inputs)
        logger.info("%s  Embeddings generated (dim=%d)", nct_id, len(vectors[0]) if vectors else 0)

    # Step 4: Upsert into Supabase
    async with async_session_factory() as session:
        try:
            await _upsert_trial(session, trial)
            await _replace_chunks(session, nct_id, chunks, vectors)
            await session.commit()
            embed_status = "no-embed" if args.skip_embed else "embedded"
            logger.info(
                "%s  Committed: %d chunks (%s)",
                nct_id,
                len(chunks),
                embed_status,
            )
        except Exception:
            await session.rollback()
            logger.error("%s  Transaction rolled back due to error", nct_id)
            raise

    return {"nct_id": nct_id, "status": "ok", "chunks": len(chunks)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    args = _parse_args()

    all_studies = _load_manifest()
    selected = _select_studies(all_studies, args)

    mode_label = "DRY RUN -- no API calls, no DB writes" if args.dry_run else "LIVE RUN"
    logger.info("SCRI Ingestion Pipeline  |  %s  |  %d trial(s) selected", mode_label, len(selected))

    results: list[dict] = []
    for i, study in enumerate(selected, start=1):
        logger.info("--- [%d/%d] Processing %s ---", i, len(selected), study["nct_id"])
        try:
            result = await _process_trial(study, args)
        except Exception:
            # Log the error but continue the batch so one bad trial doesn't
            # abort ingestion of the remaining 24 (D-8.3).
            logger.exception("Unhandled error processing %s -- skipping", study["nct_id"])
            result = {"nct_id": study["nct_id"], "status": "error", "chunks": 0}
        results.append(result)

    # Final summary report
    print("\n" + "=" * 50)
    print("INGESTION SUMMARY")
    print("=" * 50)
    total_chunks = 0
    for r in results:
        status_icon = "OK" if r["status"] in ("ok", "dry-run") else ("REFUSE" if r["status"] == "refused" else ("ERR" if r["status"] == "error" else "SKIP"))
        print(f"  [{status_icon}]  {r['nct_id']}  --  {r['chunks']} chunks  ({r['status']})")
        total_chunks += r["chunks"]
    print(f"\nTotal: {len(results)} trials  |  {total_chunks} chunks")

    if not args.dry_run:
        print("\nNext: run a Supabase query to verify row counts:")
        print("  SELECT COUNT(*) FROM clinical_trials;")
        print("  SELECT COUNT(*) FROM trial_chunks;")
        print("  SELECT COUNT(*) FROM trial_chunks WHERE embedding IS NOT NULL;")


if __name__ == "__main__":
    asyncio.run(main())
