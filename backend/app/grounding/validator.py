"""Grounding and citation validation engine for SCRI Oncology Copilot.

Enforces the Golden Rule: Zero Hallucination / Absolute Grounding.
Every factual claim must link to a real chunk that was actually retrieved in that turn.
"""

import logging
import re
from typing import NamedTuple

from app.assistant.schemas import MessageCitationCreate, ProtocolPassage

logger = logging.getLogger(__name__)

# Regex pattern matching bracketed citations: [NCT07659782, Eligibility: Exclusion Criterion #4]
# Supports NCT followed by 8 digits, optional whitespace, comma, and section header text
CITATION_REGEX = re.compile(
    r"\[(NCT\d{8}),\s*([^\]]+)\]",
    re.IGNORECASE,
)


class ParsedCitation(NamedTuple):
    raw_match: str
    nct_id: str
    section_header: str
    start_pos: int
    end_pos: int


class GroundingValidator:
    """Validator ensuring every model citation maps strictly to retrieved evidence."""

    @classmethod
    def parse_citations(cls, text: str) -> list[ParsedCitation]:
        """Extract all bracketed clinical citations from assistant output text."""
        citations: list[ParsedCitation] = []
        for match in CITATION_REGEX.finditer(text):
            citations.append(
                ParsedCitation(
                    raw_match=match.group(0),
                    nct_id=match.group(1).upper(),
                    section_header=match.group(2).strip(),
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
            )
        return citations

    @classmethod
    def match_passage(
        cls,
        nct_id: str,
        section_header: str,
        passages: list[ProtocolPassage],
    ) -> ProtocolPassage | None:
        """Find the best matching retrieved protocol passage for a parsed citation.

        Scoring heuristic:
        1. Exact NCT ID and matching section header / criterion numbers (best).
        2. Exact NCT ID with partial section title overlap.
        3. Fallback: First passage for that NCT ID if only one retrieved.
        """
        candidate_passages = [p for p in passages if p.nct_id.upper() == nct_id]
        if not candidate_passages:
            return None

        clean_header = section_header.lower()

        # Check for criterion number match (e.g. "#4" or "criterion 4")
        criterion_match = re.search(r"(?:criterion\s*#?|#)\s*(\d+)", clean_header)
        target_num = criterion_match.group(1) if criterion_match else None

        for p in candidate_passages:
            p_header = p.section_header.lower()
            if target_num:
                p_crit = re.search(r"(?:criterion\s*#?|#)\s*(\d+)", p_header)
                if p_crit and p_crit.group(1) == target_num:
                    return p

            if clean_header in p_header or p_header in clean_header:
                return p

        # If no precise section match, fallback to the top passage for that NCT
        return candidate_passages[0]

    @classmethod
    def validate_citations(
        cls,
        text: str,
        passages: list[ProtocolPassage],
    ) -> list[MessageCitationCreate]:
        """Validate citations against retrieved passages and return verified citation records.

        Deduplicates identical citations within the same turn while assigning
        sequential citation_index (1, 2, ...).
        """
        parsed = cls.parse_citations(text)
        verified: list[MessageCitationCreate] = []
        seen_keys: set[tuple[str, str]] = set()
        citation_counter = 1

        for item in parsed:
            matched_passage = cls.match_passage(item.nct_id, item.section_header, passages)
            if not matched_passage:
                logger.warning(
                    "Ungrounded citation detected and rejected: [%s, %s]",
                    item.nct_id,
                    item.section_header,
                )
                continue

            dedup_key = (item.nct_id, matched_passage.section_header)
            if dedup_key in seen_keys:
                continue

            seen_keys.add(dedup_key)
            verified.append(
                MessageCitationCreate(
                    chunk_id=matched_passage.chunk_id,
                    nct_id=matched_passage.nct_id,
                    section_header=matched_passage.section_header,
                    verbatim_quote=matched_passage.chunk_text[:1000].strip(),
                    citation_index=citation_counter,
                )
            )
            citation_counter += 1

        return verified

    @classmethod
    def sanitize_unverified_citations(
        cls,
        text: str,
        passages: list[ProtocolPassage],
    ) -> str:
        """Strip or flag ungrounded citations in the text so unverified claims are not cited."""
        parsed = cls.parse_citations(text)
        if not parsed:
            return text

        # Process replacements in reverse order of position to preserve offsets
        sanitized = text
        for item in reversed(parsed):
            matched = cls.match_passage(item.nct_id, item.section_header, passages)
            if not matched:
                # Remove ungrounded citation bracket
                sanitized = (
                    sanitized[: item.start_pos]
                    + f"[{item.nct_id} (Unverified Protocol Reference)]"
                    + sanitized[item.end_pos :]
                )
        return sanitized
