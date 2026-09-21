"""Runtime dependency container for SCRI Oncology Copilot agent turns."""

import uuid
from dataclasses import dataclass, field

from app.assistant.schemas import ProtocolPassage
from app.config import Settings, settings


@dataclass
class OncologyAgentDeps:
    """Strongly-typed runtime dependencies provided to agent turn execution."""

    user_id: uuid.UUID
    thread_id: uuid.UUID | None = None
    retrieved_passages: list[ProtocolPassage] = field(default_factory=list)
    # Trial counts per disease category (C3 / N3): lets the model truthfully
    # answer coverage questions and refuse topics outside the corpus.
    corpus_manifest: dict[str, int] = field(default_factory=dict)
    app_settings: Settings = field(default_factory=lambda: settings)
