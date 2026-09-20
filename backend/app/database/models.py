"""SQLAlchemy 2.0 declarative database models for SCRI Oncology Copilot.

Defines schemas for:
- Profile: Coordinator and investigator identities linked to Supabase Auth.
- ClinicalTrial: Landmark oncology trial protocol metadata.
- TrialChunk: Section-partitioned protocol texts with dense embeddings (pgvector) and full-text search vectors.
- ChatThread: Coordinator screening sessions.
- ChatMessage: Turn-by-turn prompts and streaming assistant completions.
- MessageCitation: Grounded, verifiable citations linking assistant assertions to verbatim protocol chunks.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Profile(Base, TimestampMixin):
    """User profile linked directly to Supabase Auth `auth.users`.
    
    Why this table is necessary:
    Enforces role-based access control (RBAC) and data tenancy. Coordinators
    can only view and resume their own clinical screening threads.
    """
    __tablename__ = "profiles"

    # UUID matching Supabase auth.users.id
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    # Role: 'coordinator', 'investigator', 'admin'
    role: Mapped[str] = mapped_column(
        String(50),
        default="coordinator",
        nullable=False,
    )

    # Relationships
    threads: Mapped[List["ChatThread"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ChatThread.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Profile {self.email} role={self.role}>"


class ClinicalTrial(Base, TimestampMixin):
    """Clinical trial protocol metadata downloaded from ClinicalTrials.gov.
    
    Why this table is necessary:
    Stores the macro-level clinical parameters (phase, sponsor, drug arms, endpoints)
    and acts as the parent anchor for all partitioned protocol chunks.
    """
    __tablename__ = "clinical_trials"

    # National Clinical Trial identifier (e.g. 'NCT07659782')
    nct_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        index=True,
    )
    # Target tumor program: 'Breast', 'Lung', 'Colorectal', 'Melanoma', 'Hematologic'
    category: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    brief_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    official_title: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    organization: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    # Status: 'RECRUITING', 'ACTIVE_NOT_RECRUITING', etc.
    status: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    # Critical clinical timeline dates
    last_update_posted_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    primary_completion_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    # Structured clinical arrays stored as JSONB
    phases: Mapped[Optional[List[Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    conditions: Mapped[Optional[List[Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    arms: Mapped[Optional[List[Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    primary_outcomes: Mapped[Optional[List[Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    chunks: Mapped[List["TrialChunk"]] = relationship(
        back_populates="trial",
        cascade="all, delete-orphan",
        order_by="TrialChunk.chunk_index.asc()",
    )

    def __repr__(self) -> str:
        return f"<ClinicalTrial {self.nct_id} category={self.category} status={self.status}>"


class TrialChunk(Base, TimestampMixin):
    """Section-aware clinical trial chunk with dense embedding and full-text vector.
    
    Why this table is necessary:
    Powerhouse of the RAG hybrid retrieval system. Stores dense semantic embeddings (1536 dims)
    for semantic similarity AND postgres tsvectors for exact oncology keyword matches (e.g. KRAS G12D).
    """
    __tablename__ = "trial_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nct_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("clinical_trials.nct_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    # Section classification: 'ELIGIBILITY_INCLUSION', 'ELIGIBILITY_EXCLUSION', 'STUDY_DESIGN', 'BRIEF_SUMMARY'
    section_type: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    # Human-readable header (e.g. 'Eligibility: Exclusion Criterion #4')
    section_header: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    # Verbatim text of this chunk
    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Dense vector representation from text-embedding-3-small (1536 dimensions)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536),
        nullable=True,
    )
    # Full-text search tsvector generated for exact oncology terms
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        nullable=True,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    trial: Mapped["ClinicalTrial"] = relationship(
        back_populates="chunks",
    )
    citations: Mapped[List["MessageCitation"]] = relationship(
        back_populates="chunk",
    )

    def __repr__(self) -> str:
        return f"<TrialChunk {self.nct_id} section={self.section_type} idx={self.chunk_index}>"


class ChatThread(Base, TimestampMixin):
    """Coordinator screening conversation thread.
    
    Why this table is necessary:
    Maintains history of clinical queries for a specific patient screening session.
    """
    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="New Screening Session",
        nullable=False,
    )

    # Relationships
    user: Mapped["Profile"] = relationship(
        back_populates="threads",
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )

    def __repr__(self) -> str:
        return f"<ChatThread {self.id} title={self.title}>"


class ChatMessage(Base, TimestampMixin):
    """Individual turn within a clinical screening chat thread.
    
    Why this table is necessary:
    Stores the prompt submitted by the coordinator and the verbatim stream generated
    by the PydanticAI agent, along with runtime latency and token telemetry.
    """
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Role: 'user', 'assistant', 'system'
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    # Markdown content of the message
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Metadata: latency_ms, tokens_used, model_name
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    thread: Mapped["ChatThread"] = relationship(
        back_populates="messages",
    )
    citations: Mapped[List["MessageCitation"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageCitation.citation_index.asc()",
    )

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} role={self.role} thread={self.thread_id}>"


class MessageCitation(Base):
    """Verifiable clinical citation linking an assistant statement to a protocol passage.
    
    Why this table is necessary:
    Enforces the Golden Rule: Zero Hallucination. Every claim made in an assistant message
    must link back to an exact NCT ID and section header. When coordinators click citation pills
    in the UI, the frontend retrieves this verbatim quote for instant audit.
    """
    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trial_chunks.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    # Denormalized for fast retrieval without joining chunks
    nct_id: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
    )
    section_header: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    verbatim_quote: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Index order in message body (e.g. [1], [2])
    citation_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    message: Mapped["ChatMessage"] = relationship(
        back_populates="citations",
    )
    chunk: Mapped[Optional["TrialChunk"]] = relationship(
        back_populates="citations",
    )

    def __repr__(self) -> str:
        return f"<MessageCitation msg={self.message_id} [{self.citation_index}] nct={self.nct_id}>"
