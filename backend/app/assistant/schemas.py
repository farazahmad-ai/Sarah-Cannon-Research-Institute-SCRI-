"""Pydantic data contracts for chat, thread management, and retrieval passages.

Defines schemas for:
- ThreadCreate: Optional title when initiating a new clinical screening thread.
- ChatRequest: Incoming message and optional thread ID.
- ThreadOut: Serialized chat thread summary for coordinators.
- MessageOut: Serialized chat message turn.
- ProtocolPassage: Grounded trial protocol passage chunk.
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ThreadCreate(BaseModel):
    """Payload for creating a new screening thread."""

    title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional title for the clinical screening session",
    )


class ChatRequest(BaseModel):
    """Incoming user chat turn request."""

    thread_id: Optional[uuid.UUID] = Field(
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


class MessageOut(BaseModel):
    """Response model for individual chat messages."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ProtocolPassage(BaseModel):
    """Protocol passage chunk representation matching retrieval output."""

    nct_id: str
    section_header: str
    chunk_text: str
