"""Unit tests for GroundingValidator and citation verification."""

import uuid

from app.assistant.schemas import ProtocolPassage
from app.grounding.validator import GroundingValidator


def _sample_passages() -> list[ProtocolPassage]:
    return [
        ProtocolPassage(
            chunk_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            nct_id="NCT07659782",
            section_type="ELIGIBILITY_EXCLUSION",
            section_header="Eligibility: Exclusion Criterion #4",
            chunk_text="Prior chemotherapy or targeted systemic therapy within 4 weeks prior to study Day 1.",
        ),
        ProtocolPassage(
            chunk_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            nct_id="NCT07659782",
            section_type="ELIGIBILITY_INCLUSION",
            section_header="Eligibility: Inclusion Criterion #2",
            chunk_text="Histologically or cytologically confirmed locally advanced or metastatic KRAS G12D mutant NSCLC.",
        ),
        ProtocolPassage(
            chunk_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            nct_id="NCT05794958",
            section_type="ELIGIBILITY_EXCLUSION",
            section_header="Eligibility: Exclusion Criterion #1",
            chunk_text="Active or untreated central nervous system (CNS) metastases or leptomeningeal disease.",
        ),
    ]


def test_parse_citations():
    text = (
        "Patients with prior chemo require a 4-week washout [NCT07659782, Eligibility: Exclusion Criterion #4]. "
        "Also requires KRAS G12D mutation [NCT07659782, Inclusion Criterion #2]."
    )
    parsed = GroundingValidator.parse_citations(text)
    assert len(parsed) == 2
    assert parsed[0].nct_id == "NCT07659782"
    assert "Exclusion Criterion #4" in parsed[0].section_header
    assert parsed[1].nct_id == "NCT07659782"
    assert "Inclusion Criterion #2" in parsed[1].section_header


def test_validate_citations_exact_match():
    passages = _sample_passages()
    text = "The patient must have a 4-week washout [NCT07659782, Eligibility: Exclusion Criterion #4]."

    citations = GroundingValidator.validate_citations(text, passages)
    assert len(citations) == 1
    c = citations[0]
    assert c.nct_id == "NCT07659782"
    assert c.chunk_id == uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert c.citation_index == 1
    assert "Prior chemotherapy" in c.verbatim_quote


def test_validate_citations_rejects_unretrieved_trial():
    passages = _sample_passages()
    # NCT09999999 was never retrieved in this turn
    text = "Fabricated statement [NCT09999999, Eligibility: Exclusion Criterion #1]."

    citations = GroundingValidator.validate_citations(text, passages)
    assert len(citations) == 0


def test_validate_citations_deduplication():
    passages = _sample_passages()
    # Same citation mentioned twice in the response
    text = (
        "First reference [NCT07659782, Eligibility: Exclusion Criterion #4]. "
        "Second reference [NCT07659782, Eligibility: Exclusion Criterion #4]."
    )

    citations = GroundingValidator.validate_citations(text, passages)
    assert len(citations) == 1
    assert citations[0].citation_index == 1


def test_sanitize_unverified_citations():
    passages = _sample_passages()
    text = (
        "Valid: [NCT07659782, Exclusion Criterion #4]. "
        "Invalid: [NCT09999999, Exclusion Criterion #1]."
    )

    sanitized = GroundingValidator.sanitize_unverified_citations(text, passages)
    assert "[NCT07659782, Exclusion Criterion #4]" in sanitized
    assert "[NCT09999999 (Unverified Protocol Reference)]" in sanitized
