"""Widen full-text search trigger to index section_header alongside chunk_text.

Revision ID: 0002_widen_fts_header
Revises: 0001_initial_oncology_schema
Create Date: 2026-09-21 02:00:00.000000

Decision Rationale (B2):
In chunker.py, embed_text includes the section_header so the vector search
can match queries against criterion titles (e.g. "Exclusion Criterion #4").
Previously, search_vector indexed only chunk_text. Widening the FTS trigger to
coalesce(section_header, '') || ' ' || coalesce(chunk_text, '') achieves full
lexical-semantic parity without modifying embeddings or re-running the embedding API.
"""

from typing import Sequence, Union
from alembic import op

# Revision identifiers, used by Alembic
revision: str = "0002_widen_fts_header"
down_revision: Union[str, None] = "0001_initial_oncology_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update function to index both section_header and chunk_text
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_trial_chunk_search_vector() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector(
                'english',
                coalesce(NEW.section_header, '') || ' ' || coalesce(NEW.chunk_text, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # 2. Re-create trigger to fire on update of either chunk_text or section_header
    op.execute("DROP TRIGGER IF EXISTS trg_trial_chunks_search_vector_update ON trial_chunks;")
    op.execute(
        """
        CREATE TRIGGER trg_trial_chunks_search_vector_update
        BEFORE INSERT OR UPDATE OF chunk_text, section_header ON trial_chunks
        FOR EACH ROW EXECUTE FUNCTION update_trial_chunk_search_vector();
        """
    )

    # 3. Backfill: touch chunk_text to force search_vector recomputation for all chunks
    op.execute("UPDATE trial_chunks SET chunk_text = chunk_text;")


def downgrade() -> None:
    # Revert function to chunk_text only
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_trial_chunk_search_vector() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', coalesce(NEW.chunk_text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_trial_chunks_search_vector_update ON trial_chunks;")
    op.execute(
        """
        CREATE TRIGGER trg_trial_chunks_search_vector_update
        BEFORE INSERT OR UPDATE OF chunk_text ON trial_chunks
        FOR EACH ROW EXECUTE FUNCTION update_trial_chunk_search_vector();
        """
    )

    op.execute("UPDATE trial_chunks SET chunk_text = chunk_text;")
