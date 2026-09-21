"""Pydantic data contracts for chat, thread management, and retrieval passages.

Defines schemas for:
- ThreadCreate: Optional title when initiating a new clinical screening thread.
- ChatRequest: Incoming message and optional thread ID.
- ThreadOut: Serialized chat thread summary for coordinators.
- MessageOut: Serialized chat message turn.
- ProtocolPassage: Grounded trial protocol passage chunk.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ThreadCreate(BaseModel):
    """Payload for creating a new screening thread."""

    title: str | None = Field(
        default=None,
        max_length=255,
        description="Optional title for the clinical screening session",
    )


class ChatRequest(BaseModel):
    """Incoming user chat turn request."""

    thread_id: uuid.UUID | None = Field(
        default=None,
        description="Target thread UUID. If None, a new thread is automatically created.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Clinical query or patient screening prompt.",
    )


class ThreadOut(BaseModel):
    """Response model for chat thread representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime


class CitationOut(BaseModel):
    """Response model for grounded message citations."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    nct_id: str
    section_header: str
    verbatim_quote: str
    citation_index: int
    created_at: datetime | None = None


class MessageCitationCreate(BaseModel):
    """Input payload for attaching a verified citation to a message."""

    chunk_id: uuid.UUID | None = None
    nct_id: str
    section_header: str
    verbatim_quote: str
    citation_index: int


class MessageOut(BaseModel):
    """Response model for individual chat messages."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    citations: list[CitationOut] = Field(default_factory=list)


class ProtocolPassage(BaseModel):
    """Protocol passage chunk representation matching retrieval output."""

    chunk_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Chunk UUID matching trial_chunks.id (RRF dedup key & MessageCitation FK)",
    )
    nct_id: str = Field(description="National Clinical Trial identifier, e.g. NCT07659782")
    section_type: str = Field(
        default="ELIGIBILITY_EXCLUSION",
        description="Section category, e.g. ELIGIBILITY_EXCLUSION",
    )
    section_header: str = Field(description="Exact section title or criterion label")
    chunk_text: str = Field(description="Verbatim protocol passage text")
    similarity: float | None = Field(
        default=None,
        description="Raw cosine similarity (1 - cosine_distance) for abstention filtering",
    )
    last_update_posted_date: date | None = Field(
        default=None,
        description="Protocol amendment date for evidence verification",
    )
    brief_title: str | None = Field(
        default=None,
        description="Brief clinical trial title for display",
    )


class TrialSummary(BaseModel):
    """Summary representation for a landmark clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    nct_id: str
    brief_title: str
    category: str
    phases: list[str] | None = None
    status: str
    organization: str | None = None
    start_date: date | None = None
    primary_completion_date: date | None = None


class TrialChunkOut(BaseModel):
    """Structured protocol chunk representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nct_id: str
    section_type: str
    section_title: str
    chunk_index: int
    chunk_text: str
    token_count: int


class TrialDetail(TrialSummary):
    """Full protocol detail for a clinical trial including all chunks."""

    official_title: str | None = None
    last_update_posted_date: date | None = None
    conditions: list[str] | None = None
    arms: list[dict[str, object]] | None = None
    primary_outcomes: list[dict[str, object]] | None = None
    chunks: list[TrialChunkOut] = Field(default_factory=list)

