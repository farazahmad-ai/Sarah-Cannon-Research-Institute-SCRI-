"""Create initial oncology schema with pgvector and full-text search.

Revision ID: 0001_initial_oncology_schema
Revises: 
Create Date: 2026-09-18 15:15:00.000000

This migration sets up:
1. PostgreSQL 'vector' extension for pgvector dense semantic embeddings.
2. Core oncology tables: profiles, clinical_trials, trial_chunks, chat_threads, chat_messages, message_citations.
3. Specialized high-performance indexes:
   - HNSW index on trial_chunks.embedding using vector_cosine_ops (m=16, ef_construction=64)
   - GIN index on trial_chunks.search_vector
   - Standard B-Tree indexes on NCT IDs, categories, section types, and user foreign keys
4. Postgres trigger to automatically keep search_vector synced with chunk_text on insert/update.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID


# Revision identifiers, used by Alembic
revision: str = "0001_initial_oncology_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Enable PostgreSQL Vector Extension
    # -------------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # -------------------------------------------------------------------------
    # 2. Table: profiles (Research Coordinators & Investigators)
    # -------------------------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), server_default="coordinator", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_profiles_email", "profiles", ["email"], unique=True)

    # -------------------------------------------------------------------------
    # 3. Table: clinical_trials (Protocol Metadata from ClinicalTrials.gov)
    # -------------------------------------------------------------------------
    op.create_table(
        "clinical_trials",
        sa.Column("nct_id", sa.String(32), primary_key=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("brief_title", sa.String(500), nullable=False),
        sa.Column("official_title", sa.Text(), nullable=True),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("status", sa.String(100), nullable=False),
        sa.Column("last_update_posted_date", sa.Date(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("primary_completion_date", sa.Date(), nullable=True),
        sa.Column("phases", JSONB(), nullable=True),
        sa.Column("conditions", JSONB(), nullable=True),
        sa.Column("arms", JSONB(), nullable=True),
        sa.Column("primary_outcomes", JSONB(), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_clinical_trials_nct_id", "clinical_trials", ["nct_id"], unique=False)
    op.create_index("ix_clinical_trials_category", "clinical_trials", ["category"], unique=False)
    op.create_index("ix_clinical_trials_status", "clinical_trials", ["status"], unique=False)

    # -------------------------------------------------------------------------
    # 4. Table: trial_chunks (Dense Embeddings & Text Corpus for Hybrid Search)
    # -------------------------------------------------------------------------
    op.create_table(
        "trial_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("nct_id", sa.String(32), sa.ForeignKey("clinical_trials.nct_id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_type", sa.String(100), nullable=False),
        sa.Column("section_header", sa.String(255), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trial_chunks_nct_id", "trial_chunks", ["nct_id"], unique=False)
    op.create_index("ix_trial_chunks_section_type", "trial_chunks", ["section_type"], unique=False)

    # High-performance HNSW index for sub-100ms pgvector cosine distance search
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_trial_chunks_embedding_hnsw "
        "ON trial_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    )

    # GIN index on search_vector for exact oncology term matching (e.g. KRAS G12D, EGFR Exon 20)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_trial_chunks_search_vector_gin "
        "ON trial_chunks USING gin (search_vector);"
    )

    # PostgreSQL Trigger to keep search_vector automatically synced with chunk_text
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
    op.execute(
        """
        CREATE TRIGGER trg_trial_chunks_search_vector_update
        BEFORE INSERT OR UPDATE OF chunk_text ON trial_chunks
        FOR EACH ROW EXECUTE FUNCTION update_trial_chunk_search_vector();
        """
    )

    # -------------------------------------------------------------------------
    # 5. Table: chat_threads (Screening Sessions)
    # -------------------------------------------------------------------------
    op.create_table(
        "chat_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), server_default="New Screening Session", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"], unique=False)

    # -------------------------------------------------------------------------
    # 6. Table: chat_messages (Individual Turns)
    # -------------------------------------------------------------------------
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"], unique=False)

    # -------------------------------------------------------------------------
    # 7. Table: message_citations (Clinical Grounding Audit Trail)
    # -------------------------------------------------------------------------
    op.create_table(
        "message_citations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("trial_chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nct_id", sa.String(32), nullable=False),
        sa.Column("section_header", sa.String(255), nullable=False),
        sa.Column("verbatim_quote", sa.Text(), nullable=False),
        sa.Column("citation_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"], unique=False)
    op.create_index("ix_message_citations_chunk_id", "message_citations", ["chunk_id"], unique=False)
    op.create_index("ix_message_citations_nct_id", "message_citations", ["nct_id"], unique=False)


def downgrade() -> None:
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_trial_chunks_search_vector_update ON trial_chunks;")
    op.execute("DROP FUNCTION IF EXISTS update_trial_chunk_search_vector;")

    # Drop tables in reverse order of foreign key dependency
    op.drop_table("message_citations")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_table("trial_chunks")
    op.drop_table("clinical_trials")
    op.drop_table("profiles")
