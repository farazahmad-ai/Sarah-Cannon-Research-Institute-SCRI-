"""Section-aware protocol chunker for SCRI Oncology Copilot.

Converts structured ClinicalTrials.gov JSON into atomic, citation-ready
ChunkPayload objects aligned on clinical boundaries -- never splitting a
numbered criterion, lab threshold, or washout clause across chunks.

Design rationale:
- We parse by JSON key path, not by character or token count, because
  ClinicalTrials.gov data has explicit semantic sections.
- Each eligibility bullet (* ...) becomes its own candidate chunk so that
  pgvector can retrieve a single criterion for a single coordinator query.
- A context prefix ([NCT ID | Phase | Category | Section]) is prepended to
  every chunk text before embedding so the vector captures both the clinical
  content AND the trial identity simultaneously.
- Token counting uses a simple whitespace estimator (word_count * 1.3) to
  avoid importing tiktoken as a runtime dependency. Precision is not critical
  here -- we only need to enforce a soft ceiling to avoid oversized chunks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Token ceiling note: a soft 600-token limit was originally planned but never
# enforced (splitting a criterion mid-clause would break citation integrity).
# Oversized chunks are logged as warnings during ingestion instead.
# ---------------------------------------------------------------------------


@dataclass
class ParsedTrial:
    """Structured container built from a raw ClinicalTrials.gov JSON file."""

    nct_id: str
    category: str           # e.g. 'non_small_cell_lung_cancer'
    brief_title: str
    official_title: str
    organization: str
    status: str
    last_update_posted_date: date | None
    start_date: date | None
    primary_completion_date: date | None
    phases: list[str]
    conditions: list[str]
    arms: list[dict[str, Any]]
    primary_outcomes: list[dict[str, Any]]
    source_url: str

    # Raw text sections extracted from protocolSection keys
    brief_summary: str
    detailed_description: str
    eligibility_criteria_raw: str   # full blob: "Inclusion Criteria:\n\n* ..."


@dataclass
class ChunkPayload:
    """A single embeddable unit of protocol text ready for DB insertion.

    Every field maps directly to a column in the trial_chunks table.
    The embed_text field is what gets sent to the embedding API -- it includes
    the context prefix so the vector encodes trial identity alongside content.
    """

    nct_id: str
    chunk_index: int
    section_type: str       # BRIEF_SUMMARY | STUDY_DESIGN | ELIGIBILITY_INCLUSION | ELIGIBILITY_EXCLUSION
    section_header: str     # Human-readable citation label, e.g. "Eligibility: Inclusion Criterion #3"
    chunk_text: str         # Verbatim protocol text (stored in DB, shown in citation popover)
    embed_text: str         # chunk_text with context prefix (sent to embedding API only)
    token_count: int
    metadata_json: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_trial_json(json_path: Path) -> ParsedTrial:
    """Parse a ClinicalTrials.gov raw JSON file into a ParsedTrial.

    Navigates the protocolSection key hierarchy directly rather than
    deserializing the entire blob into a generic dict and guessing fields.
    """
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    proto = raw.get("protocolSection", {})

    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    desc = proto.get("descriptionModule", {})
    design = proto.get("designModule", {})
    arms_mod = proto.get("armsInterventionsModule", {})
    outcomes = proto.get("outcomesModule", {})
    elig = proto.get("eligibilityModule", {})
    sponsor = proto.get("sponsorCollaboratorsModule", {})

    return ParsedTrial(
        nct_id=ident.get("nctId", ""),
        category="",                        # injected by pipeline from manifest
        brief_title=ident.get("briefTitle", ""),
        official_title=ident.get("officialTitle", ""),
        organization=sponsor.get("leadSponsor", {}).get("name", ""),
        status=status_mod.get("overallStatus", ""),
        last_update_posted_date=_parse_date(
            status_mod.get("lastUpdatePostDateStruct", {}).get("date")
        ),
        start_date=_parse_date(
            status_mod.get("startDateStruct", {}).get("date")
        ),
        primary_completion_date=_parse_date(
            status_mod.get("primaryCompletionDateStruct", {}).get("date")
        ),
        phases=design.get("phases", []),
        conditions=proto.get("conditionsModule", {}).get("conditions", []),
        arms=arms_mod.get("armGroups", []),
        primary_outcomes=outcomes.get("primaryOutcomes", []),
        source_url=f"https://clinicaltrials.gov/study/{ident.get('nctId', '')}",
        brief_summary=desc.get("briefSummary", "").strip(),
        detailed_description=desc.get("detailedDescription", "").strip(),
        eligibility_criteria_raw=elig.get("eligibilityCriteria", "").strip(),
    )


def chunk_protocol(trial: ParsedTrial) -> list[ChunkPayload]:
    """Convert a ParsedTrial into an ordered list of ChunkPayload objects.

    Chunking order:
      1. BRIEF_SUMMARY  -- one chunk (plain-language trial description)
      2. STUDY_DESIGN   -- one chunk (objectives, outline, arms summary)
      3. ELIGIBILITY_INCLUSION -- one chunk per inclusion criterion bullet
      4. ELIGIBILITY_EXCLUSION -- one chunk per exclusion criterion bullet

    Each chunk receives a context prefix prepended for embedding only so
    that cosine similarity retrieval captures both the criterion text AND
    the trial's disease category, phase, and NCT identity.
    """
    chunks: list[ChunkPayload] = []
    phase_label = _format_phase(trial.phases)
    context_prefix = f"[{trial.nct_id} | {phase_label} | {trial.category}]"

    # 1. Brief summary chunk
    if trial.brief_summary:
        chunks.append(_make_chunk(
            trial=trial,
            index=len(chunks),
            section_type="BRIEF_SUMMARY",
            section_header="Brief Summary",
            text=trial.brief_summary,
            context_prefix=context_prefix,
        ))

    # 2. Study design chunk (detailed description -- objectives + arms outline)
    if trial.detailed_description:
        chunks.append(_make_chunk(
            trial=trial,
            index=len(chunks),
            section_type="STUDY_DESIGN",
            section_header="Study Design & Objectives",
            text=trial.detailed_description,
            context_prefix=context_prefix,
        ))

    # 3 & 4. Eligibility criteria -- split into inclusion vs. exclusion, then
    #         into individual criterion bullets.
    inc_bullets, exc_bullets = _split_eligibility(trial.eligibility_criteria_raw)

    for criterion_num, bullet_text in enumerate(inc_bullets, start=1):
        chunks.append(_make_chunk(
            trial=trial,
            index=len(chunks),
            section_type="ELIGIBILITY_INCLUSION",
            section_header=f"Eligibility: Inclusion Criterion #{criterion_num}",
            text=bullet_text,
            context_prefix=context_prefix,
        ))

    for criterion_num, bullet_text in enumerate(exc_bullets, start=1):
        chunks.append(_make_chunk(
            trial=trial,
            index=len(chunks),
            section_type="ELIGIBILITY_EXCLUSION",
            section_header=f"Eligibility: Exclusion Criterion #{criterion_num}",
            text=bullet_text,
            context_prefix=context_prefix,
        ))

    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    trial: ParsedTrial,
    index: int,
    section_type: str,
    section_header: str,
    text: str,
    context_prefix: str,
) -> ChunkPayload:
    """Build a ChunkPayload, computing token estimate and embed_text."""
    clean_text = _clean_text(text)
    embed_text = f"{context_prefix}\n{section_header}\n{clean_text}"
    return ChunkPayload(
        nct_id=trial.nct_id,
        chunk_index=index,
        section_type=section_type,
        section_header=section_header,
        chunk_text=clean_text,
        embed_text=embed_text,
        token_count=_estimate_tokens(embed_text),
        metadata_json={
            "category": trial.category,
            "phases": trial.phases,
            "status": trial.status,
            "last_update_posted_date": (
                str(trial.last_update_posted_date)
                if trial.last_update_posted_date
                else None
            ),
        },
    )


def _split_eligibility(raw: str) -> tuple[list[str], list[str]]:
    """Split the raw eligibilityCriteria blob into inclusion and exclusion lists.

    ClinicalTrials.gov protocols use several heading variants that all mean the
    same thing -- the regex must tolerate all of them:

      Standard:   "Exclusion Criteria:"   (original assumption)
      With prefix: "Key Exclusion Criteria:"  (breaks \\n-anchor + literal match)
      No colon:   "Exclusion Criteria"    (colon optional)
      Casing:     any mix of upper/lower

    Fix (D-1): use MULTILINE so ^ matches any line start, make the "Key" prefix
    optional, and make the trailing colon optional.
    """
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Matches the exclusion heading at the start of any line, with or without
    # a "Key" prefix and with or without a trailing colon.
    exc_pattern = re.compile(
        r"^\s*(?:key\s+)?exclusion\s+criteria\s*:?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = exc_pattern.search(raw)

    if match:
        inclusion_raw = raw[: match.start()]
        exclusion_raw = raw[match.end():]
    else:
        inclusion_raw = raw
        exclusion_raw = ""

    # Strip the "Inclusion Criteria:" header (same variant-tolerant pattern)
    inc_header_pattern = re.compile(
        r"^\s*(?:key\s+)?inclusion\s+criteria\s*:?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    inclusion_raw = inc_header_pattern.sub("", inclusion_raw, count=1).strip()

    return _parse_bullets(inclusion_raw), _parse_bullets(exclusion_raw)


def _parse_bullets(text: str) -> list[str]:
    """Extract top-level bullet items from a criteria block.

    Handles two list styles used by ClinicalTrials.gov protocols:
      * Star bullets:    "* criterion text"
      * Numbered lists:  "1. criterion text" or "1) criterion text"

    Sub-bullets (indented "  * ") are kept attached to their parent criterion
    because they carry qualifying conditions (e.g. sub-thresholds, footnotes).
    We never break a criterion from its sub-bullets.

    Fix (D-2): the original splitter only recognised "* " bullets, causing five
    protocols that use numbered lists to collapse into a single oversized chunk.

    Example input (numbered):
      1. Must have EGFR confirmed mutation
         * Note: tested within 6 months
      2. Prior therapy washout >= 14 days

    Returns two items:
      ["Must have EGFR confirmed mutation\n  * Note: tested within 6 months",
       "Prior therapy washout >= 14 days"]
    """
    if not text.strip():
        return []

    # Match top-level bullets: "* " OR a number followed by "." or ")" and a space.
    # The lookahead ensures we only split at line-start markers, not mid-text.
    parts = re.split(r"\n(?=(?:\* |\d+[.)\s]\s*))", text.strip())
    bullets: list[str] = []

    for part in parts:
        # Strip the leading bullet marker ("* ", "1. ", "2) ", etc.)
        cleaned = re.sub(r"^(?:\* |\d+[.)\s]\s+)", "", part.strip())
        if cleaned:
            bullets.append(_clean_text(cleaned))

    return bullets


def _clean_text(text: str) -> str:
    """Normalize whitespace and remove markdown escape artifacts.

    ClinicalTrials.gov JSON contains escaped brackets \\[ \\] and
    comparison operators \\< \\> which are markdown rendering artifacts.
    We clean these so embeddings reflect the actual clinical content.
    """
    # Remove backslash escapes before brackets and operators
    text = re.sub(r"\\([<>\[\]\\])", r"\1", text)
    # Collapse 3+ consecutive newlines into double newline
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize multiple spaces (preserve newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _estimate_tokens(text: str) -> int:
    """Rough token count: word_count x 1.3 (GPT tokenizer average).

    Avoids importing tiktoken as a hard runtime dependency. The 1.3 multiplier
    accounts for subword tokenization where medical terms like 'non-small-cell'
    split into multiple tokens.
    """
    return int(len(text.split()) * 1.3)


def _format_phase(phases: list[str]) -> str:
    """Convert ['PHASE1', 'PHASE2'] into 'Phase 1/2' for context prefix."""
    if not phases:
        return "Unknown Phase"
    nums = [p.replace("PHASE", "") for p in phases]
    return f"Phase {'/'.join(nums)}"


def _parse_date(value: str | None) -> date | None:
    """Parse partial ClinicalTrials.gov dates like '2026-04' or '2026-04-01'."""
    if not value:
        return None
    parts = value.split("-")
    try:
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 2:
            # Partial date -- use first day of the month
            return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        return None
    return None
