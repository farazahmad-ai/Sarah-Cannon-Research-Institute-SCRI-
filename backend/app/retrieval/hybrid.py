"""Unified hybrid retrieval orchestrator combining pgvector and PostgreSQL FTS."""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import ProtocolPassage
from app.retrieval.fts_search import FTS_TOP_K, fts_search
from app.retrieval.rrf import RRF_K, reciprocal_rank_fusion
from app.retrieval.vector_search import VECTOR_TOP_K, vector_search

logger = logging.getLogger(__name__)

# Default top-k passages returned to the chat orchestrator
DEFAULT_LIMIT: int = 12

# Default minimum cosine similarity floor for vector relevance
DEFAULT_MIN_SIMILARITY: float = 0.30

# ---------------------------------------------------------------------------
# Entity relevance gate (audit finding C3 / remediation N4)
#
# The similarity floor measures query<->chunk closeness, not whether the passage
# is about the same clinical subject. Generic query scaffolding ("inclusion
# criteria", "protocols") inflates similarity against ANY eligibility chunk, so
# an off-corpus question like "pediatric glioblastoma protocols" can still
# surface unrelated breast/NSCLC passages — which the model then treats as a
# licence to answer. This gate abstains when none of the question's specific
# clinical terms appear in any retrieved passage.
# ---------------------------------------------------------------------------

_GENERIC_QUERY_TERMS: frozenset[str] = frozenset({
    # interrogatives / connectives
    "what", "which", "when", "where", "does", "did", "are", "was", "were", "the",
    "and", "for", "with", "from", "that", "this", "our", "have", "has", "had",
    "you", "your", "can", "could", "would", "should", "must", "may", "might",
    "will", "shall", "how", "why", "who", "whom", "whose", "than", "then",
    "them", "they", "there", "here", "into", "upon", "during", "versus",
    "between", "also", "etc", "please", "cite", "cited", "confirm", "exact",
    "specific", "text", "section", "answer", "question", "contain", "contains",
    "any",
    # trial-document scaffolding
    "criteria", "criterion", "inclusion", "exclusion", "eligibility",
    "eligible", "protocol", "protocols", "trial", "trials", "study", "studies",
    "system", "patient", "patients", "participant", "participants",
    "subject", "subjects", "treatment", "treatments", "therapy", "therapies",
    "therapeutic", "dose", "doses", "dosing", "period", "periods", "phase",
    "require", "required", "requires", "requirement", "requirements",
    "permit", "permits", "permitted", "allow", "allows", "allowed",
    "prohibit", "prohibits", "prohibited", "state", "stated", "states",
    "specify", "specifies", "specified", "mention", "mentions", "mentioned",
    "active", "compare", "comparison", "across", "level", "levels", "limit",
    "limits", "threshold", "thresholds", "value", "values", "guideline",
    "guidelines", "prior", "following", "before", "after", "first", "least",
    "number",
})

_ENTITY_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NCT_ID_RE = re.compile(r"NCT\d{8}", re.IGNORECASE)
MIN_ENTITY_MATCHES: int = 2


def extract_entity_terms(query: str) -> set[str]:
    """Extract specific clinical terms from a coordinator query."""
    tokens = _ENTITY_TOKEN_RE.findall(query.lower())
    return {
        t
        for t in tokens
        if len(t) >= 3 and t not in _GENERIC_QUERY_TERMS
    }


def _count_matching_terms(passage: ProtocolPassage, terms: set[str]) -> int:
    """Count how many distinct query terms occur in the passage's searchable text."""
    haystack = " ".join(
        filter(
            None,
            (
                passage.chunk_text,
                passage.section_header,
                passage.brief_title or "",
                passage.nct_id,
            ),
        )
    ).lower()
    return sum(1 for term in terms if term in haystack)


def _query_nct_ids(query: str) -> set[str]:
    """Explicit NCT identifiers named in the question, uppercased."""
    return {m.upper() for m in _NCT_ID_RE.findall(query)}


def apply_entity_gate(
    query: str,
    passages: list[ProtocolPassage],
) -> list[ProtocolPassage]:
    """Drop passages that share too few specific clinical terms with the question.

    Returns [] when the question names a clinical subject that appears nowhere
    (or only incidentally) in the retrieved passages — the abstention signal that
    triggers the deterministic no-evidence refusal in the orchestrator.

    Exception: if the question explicitly names an NCT identifier, only passages
    belonging to that trial are on-topic. If none match, the trial is off-corpus.
    """
    terms = extract_entity_terms(query)
    if not terms or not passages:
        return passages

    pinned_trials = _query_nct_ids(query)

    # A single specific term only proves relevance if the question only had one.
    required = min(MIN_ENTITY_MATCHES, len(terms))

    kept = [
        p
        for p in passages
        if p.nct_id.upper() in pinned_trials
        or _count_matching_terms(p, terms) >= required
    ]
    if not kept:
        logger.info(
            "Entity gate: abstaining — no retrieved passage matched >=%d of query terms %s",
            required,
            sorted(terms),
        )
    return kept


def apply_similarity_floor(
    passages: list[ProtocolPassage],
    floor: float | None,
    *,
    vector_search_healthy: bool = True,
    preserve_top_lexical: int = 0,
) -> list[ProtocolPassage]:
    """Filter candidate passages by similarity floor to enforce protocol silence."""
    if floor is None:
        return passages

    filtered: list[ProtocolPassage] = []
    lexical_preserved = 0

    for p in passages:
        if p.similarity is not None:
            if p.similarity >= floor:
                filtered.append(p)
        elif not vector_search_healthy:
            filtered.append(p)
        elif preserve_top_lexical > 0 and lexical_preserved < preserve_top_lexical:
            filtered.append(p)
            lexical_preserved += 1

    return filtered


async def retrieve_protocols(
    session: AsyncSession,
    query: str,
    *,
    disease_category: str | None = None,
    limit: int = DEFAULT_LIMIT,
    min_similarity: float | None = DEFAULT_MIN_SIMILARITY,
    preserve_top_lexical: int = 2,
) -> list[ProtocolPassage]:
    """Retrieve grounded clinical protocol passages using hybrid search."""
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    # Step 1: Sequential retrieval (B3 - never asyncio.gather on AsyncSession)
    vector_search_healthy = True
    vector_passages: list[ProtocolPassage] = []
    try:
        vector_passages = await vector_search(
            session,
            cleaned_query,
            disease_category=disease_category,
            limit=VECTOR_TOP_K,
        )
    except Exception as exc:  # noqa: BLE001
        vector_search_healthy = False
        logger.warning("Vector search failed during hybrid retrieval; falling back to FTS: %s", exc)

    fts_passages: list[ProtocolPassage] = []
    try:
        fts_passages = await fts_search(
            session,
            cleaned_query,
            disease_category=disease_category,
            limit=FTS_TOP_K,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("FTS search failed during hybrid retrieval: %s", exc)

    if not vector_passages and not fts_passages:
        return []

    # Step 2: Index passages by chunk_id
    passages_by_id: dict[uuid.UUID, ProtocolPassage] = {}
    for p in fts_passages:
        passages_by_id[p.chunk_id] = p
    for p in vector_passages:
        passages_by_id[p.chunk_id] = p

    # Step 3: Reciprocal Rank Fusion (k=60)
    ranked_lists = [
        [p.chunk_id for p in vector_passages],
        [p.chunk_id for p in fts_passages],
    ]
    fused_ranked = reciprocal_rank_fusion(ranked_lists, k=RRF_K)

    # Step 4: Assemble fused candidates and apply similarity floor (B5)
    candidates: list[ProtocolPassage] = []
    for chunk_id, _fused_score in fused_ranked:
        passage = passages_by_id.get(chunk_id)
        if passage:
            candidates.append(passage)

    floored_passages = apply_similarity_floor(
        candidates,
        min_similarity,
        vector_search_healthy=vector_search_healthy,
        preserve_top_lexical=preserve_top_lexical,
    )

    # Step 5: Entity relevance gate (audit finding C3)
    gated_passages = apply_entity_gate(cleaned_query, floored_passages)

    return gated_passages[:limit]
