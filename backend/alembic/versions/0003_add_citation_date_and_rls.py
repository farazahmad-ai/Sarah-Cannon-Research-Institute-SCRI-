"""Add last_update_posted_date to message_citations and enable Row Level Security.

Revision ID: 0003_citation_date_rls
Revises: 0002_widen_fts_header
Create Date: 2026-09-21 16:00:00.000000

Decision Rationale:
- C2: Grounding citations must carry the protocol's last_update_posted_date (amendment date)
  so coordinators verify evidence against actual amendment dates instead of row insert times.
- M4: Enable Row Level Security (RLS) policies on user-scoped tables (profiles, chat_threads,
  chat_messages, message_citations) and grant public select on public clinical trials/chunks.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# Revision identifiers, used by Alembic
revision: str = "0003_citation_date_rls"
down_revision: str | None = "0002_widen_fts_header"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add last_update_posted_date column to message_citations (C2)
    op.add_column(
        "message_citations",
        sa.Column("last_update_posted_date", sa.Date(), nullable=True),
    )

    # 2. Enable Row Level Security and add policies (M4)
    # Profiles table: user can only access their own profile
    op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'profiles_user_policy'
            ) THEN
                CREATE POLICY profiles_user_policy ON profiles
                    FOR ALL
                    USING (id = auth.uid())
                    WITH CHECK (id = auth.uid());
            END IF;
        END $$;
        """
    )

    # Chat threads table: coordinator can only access their own threads
    op.execute("ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'chat_threads' AND policyname = 'chat_threads_user_policy'
            ) THEN
                CREATE POLICY chat_threads_user_policy ON chat_threads
                    FOR ALL
                    USING (user_id = auth.uid())
                    WITH CHECK (user_id = auth.uid());
            END IF;
        END $$;
        """
    )

    # Chat messages table: messages accessible only through thread ownership
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'chat_messages' AND policyname = 'chat_messages_user_policy'
            ) THEN
                CREATE POLICY chat_messages_user_policy ON chat_messages
                    FOR ALL
                    USING (
                        EXISTS (
                            SELECT 1 FROM chat_threads
                            WHERE chat_threads.id = chat_messages.thread_id
                              AND chat_threads.user_id = auth.uid()
                        )
                    )
                    WITH CHECK (
                        EXISTS (
                            SELECT 1 FROM chat_threads
                            WHERE chat_threads.id = chat_messages.thread_id
                              AND chat_threads.user_id = auth.uid()
                        )
                    );
            END IF;
        END $$;
        """
    )

    # Message citations table: citations accessible through message -> thread ownership
    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'message_citations' AND policyname = 'message_citations_user_policy'
            ) THEN
                CREATE POLICY message_citations_user_policy ON message_citations
                    FOR ALL
                    USING (
                        EXISTS (
                            SELECT 1 FROM chat_messages
                            JOIN chat_threads ON chat_threads.id = chat_messages.thread_id
                            WHERE chat_messages.id = message_citations.message_id
                              AND chat_threads.user_id = auth.uid()
                        )
                    )
                    WITH CHECK (
                        EXISTS (
                            SELECT 1 FROM chat_messages
                            JOIN chat_threads ON chat_threads.id = chat_messages.thread_id
                            WHERE chat_messages.id = message_citations.message_id
                              AND chat_threads.user_id = auth.uid()
                        )
                    );
            END IF;
        END $$;
        """
    )

    # Public trials and chunks: read-only access for all authenticated & anon users
    op.execute("ALTER TABLE clinical_trials ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'clinical_trials' AND policyname = 'clinical_trials_public_read'
            ) THEN
                CREATE POLICY clinical_trials_public_read ON clinical_trials
                    FOR SELECT
                    USING (true);
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE trial_chunks ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies WHERE tablename = 'trial_chunks' AND policyname = 'trial_chunks_public_read'
            ) THEN
                CREATE POLICY trial_chunks_public_read ON trial_chunks
                    FOR SELECT
                    USING (true);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Drop RLS policies and disable RLS
    op.execute("DROP POLICY IF EXISTS trial_chunks_public_read ON trial_chunks;")
    op.execute("ALTER TABLE trial_chunks DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS clinical_trials_public_read ON clinical_trials;")
    op.execute("ALTER TABLE clinical_trials DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS message_citations_user_policy ON message_citations;")
    op.execute("ALTER TABLE message_citations DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS chat_messages_user_policy ON chat_messages;")
    op.execute("ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS chat_threads_user_policy ON chat_threads;")
    op.execute("ALTER TABLE chat_threads DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS profiles_user_policy ON profiles;")
    op.execute("ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;")

    # Drop column
    op.drop_column("message_citations", "last_update_posted_date")
