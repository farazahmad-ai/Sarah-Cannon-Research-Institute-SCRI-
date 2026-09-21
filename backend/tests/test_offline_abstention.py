"""Offline unit tests verifying abstention behavior at the shipping production threshold.

Covers audit findings M2 and C3:
- Passages with similarity < 0.30 (DEFAULT_MIN_SIMILARITY) are rejected.
- An empty retrieval result produces a REFUSAL DIRECTIVE, not a status line,
  so the model is instructed to refuse rather than answer from memory.
- The entity relevance gate abstains on off-corpus questions (e.g. pediatric
  glioblastoma) while preserving on-corpus questions (e.g. KRAS G12D).
- The deterministic no-evidence refusal names the actual corpus scope.

The earlier version of this file asserted that a string literal existed inside
SYSTEM_PROMPT — a tautology that could not fail and gave false assurance. These
tests assert behaviour of the actual refusal machinery instead.
"""

import uuid

from app.assistant.prompts import (
    SYSTEM_PROMPT,
    build_no_evidence_refusal,
    format_corpus_manifest,
    format_protocol_context,
)
from app.assistant.schemas import ProtocolPassage
from app.retrieval.hybrid import (
    DEFAULT_MIN_SIMILARITY,
    apply_entity_gate,
    apply_similarity_floor,
    extract_entity_terms,
)

_CORPUS = {
    "breast_cancer": 5,
    "non_small_cell_lung_cancer": 5,
    "colorectal_cancer": 5,
    "melanoma": 5,
    "lymphoma_car_t": 5,
}


def _make_passage(
    similarity: float | None,
    nct_id: str = "NCT05794958",
    header: str = "Eligibility: Exclusion Criterion #4",
    text: str = "Prior systemic anti-cancer therapy within 28 days.",
    brief_title: str | None = "Axicabtagene Ciloleucel reinfusion study",
) -> ProtocolPassage:
    return ProtocolPassage(
        chunk_id=uuid.uuid4(),
        nct_id=nct_id,
        section_type="ELIGIBILITY_EXCLUSION",
        section_header=header,
        chunk_text=text,
        similarity=similarity,
        brief_title=brief_title,
    )


# ---------------------------------------------------------------------------
# Similarity floor at the shipping threshold (M2)
# ---------------------------------------------------------------------------


def test_abstention_floor_rejects_below_shipping_threshold():
    """Candidates below shipping threshold (0.30) must be discarded."""
    irrelevant_passages = [
        _make_passage(similarity=0.12),
        _make_passage(similarity=0.28),
        _make_passage(similarity=0.299),
    ]

    accepted = apply_similarity_floor(
        irrelevant_passages,
        floor=DEFAULT_MIN_SIMILARITY,
        vector_search_healthy=True,
    )
    assert len(accepted) == 0, f"Expected 0 passages, got {len(accepted)}"


def test_abstention_floor_accepts_at_or_above_shipping_threshold():
    """Candidates meeting or exceeding 0.30 must be accepted."""
    passages = [
        _make_passage(similarity=0.29),
        _make_passage(similarity=0.30),
        _make_passage(similarity=0.55),
    ]

    accepted = apply_similarity_floor(
        passages,
        floor=DEFAULT_MIN_SIMILARITY,
        vector_search_healthy=True,
    )
    assert len(accepted) == 2
    assert all(p.similarity is not None and p.similarity >= 0.30 for p in accepted)


# ---------------------------------------------------------------------------
# Empty-context directive is an instruction, not a status line (C3)
# ---------------------------------------------------------------------------


def test_empty_context_is_a_refusal_directive():
    """When no passages pass the floor, context must instruct refusal, not just report absence."""
    context = format_protocol_context([])

    # It must be an instruction the model can act on...
    assert "MUST NOT" in context or "must not" in context.lower()
    # ...and it must explicitly forbid answering from general knowledge.
    assert "general medical knowledge" in context
    # The old, dangerous status-line phrasing must be gone.
    assert "No matching protocol passages retrieved for this query" not in context


def test_system_prompt_forbids_answering_from_training_knowledge():
    """Rule 0 must exist and must prohibit off-corpus answers, not just fabricated criteria."""
    assert "ANSWER ONLY FROM THE PROVIDED PROTOCOL CONTEXT" in SYSTEM_PROMPT
    assert "FORBIDDEN" in SYSTEM_PROMPT
    # The refusal phrasing the model must produce for off-corpus questions.
    assert "does not contain protocol information" in SYSTEM_PROMPT


def test_system_prompt_still_enforces_negative_refusal_for_missing_criteria():
    """The original negative-refusal rule (protocol silence) must survive the rewrite."""
    assert "The protocol does not state [X]" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Deterministic no-evidence refusal (C3 / N1)
# ---------------------------------------------------------------------------


def test_no_evidence_refusal_names_corpus_scope():
    """The canned refusal must state what the system actually contains."""
    refusal = build_no_evidence_refusal(
        "What are the inclusion criteria for pediatric glioblastoma multiforme protocols?",
        _CORPUS,
    )

    assert "cannot answer" in refusal
    assert "25" in refusal  # total trial count from the manifest
    assert "breast cancer" in refusal
    # It must refuse to answer from general knowledge.
    assert "general medical knowledge" in refusal
    # It must not contain any NCT citation — there is nothing to cite.
    assert "NCT" not in refusal


def test_no_evidence_refusal_handles_empty_corpus():
    """With no trials loaded, the refusal must say so rather than crash."""
    refusal = build_no_evidence_refusal("anything", {})
    assert "no trial protocols" in refusal


def test_no_evidence_refusal_truncates_long_queries():
    """A 500-character question must not produce a 500-character echo in the refusal."""
    long_query = "question about " + "x" * 400
    refusal = build_no_evidence_refusal(long_query, _CORPUS)
    assert len(refusal) < 1000


def test_corpus_manifest_lists_all_categories():
    """The manifest must enumerate every disease area so coverage questions are answerable."""
    manifest = format_corpus_manifest(_CORPUS)
    assert "25" in manifest
    for area in ("breast", "lung", "colorectal", "melanoma", "lymphoma"):
        assert area in manifest
    assert format_corpus_manifest({}) == (
        "Corpus Manifest: no clinical trials are currently loaded in this system."
    )


# ---------------------------------------------------------------------------
# Entity relevance gate (C3 / N4)
# ---------------------------------------------------------------------------


def test_entity_gate_abstains_on_off_corpus_disease():
    """The pediatric GBM case: unrelated eligibility chunks must be dropped, not delivered.

    This is the exact regression test for the observed hallucination — generic
    scaffolding ('inclusion criteria') must not let breast/NSCLC chunks through
    when the question asks about a disease absent from the corpus.
    """
    irrelevant = [
        _make_passage(
            similarity=0.42,
            nct_id="NCT06393374",
            header="Eligibility: Inclusion Criterion #1",
            text="Histologically confirmed HER2-low metastatic breast cancer.",
            brief_title="Breast ADC trial",
        ),
        _make_passage(
            similarity=0.35,
            nct_id="NCT07659782",
            header="Eligibility: Inclusion Criterion #2",
            text="KRAS G12D mutant NSCLC confirmed by tissue biopsy.",
            brief_title="KRAS G12D NSCLC trial",
        ),
    ]

    query = (
        "What are the inclusion criteria for pediatric glioblastoma "
        "multiforme protocols in this system?"
    )

    assert apply_entity_gate(query, irrelevant) == []


def test_entity_gate_preserves_on_corpus_queries():
    """A KRAS G12D question must keep KRAS G12D passages."""
    relevant = [
        _make_passage(
            similarity=0.55,
            nct_id="NCT07659782",
            header="Eligibility: Inclusion Criterion #2",
            text="KRAS G12D mutant NSCLC confirmed by tissue biopsy.",
        ),
        _make_passage(
            similarity=0.40,
            nct_id="NCT06393374",
            header="Eligibility: Inclusion Criterion #1",
            text="Histologically confirmed HER2-low metastatic breast cancer.",
        ),
    ]

    kept = apply_entity_gate("KRAS G12D mutation inclusion criteria", relevant)
    assert relevant[0] in kept


def test_entity_gate_passes_fully_generic_queries():
    """A question with no specific terms must never trigger abstention."""
    generic = [_make_passage(similarity=0.4)]
    assert apply_entity_gate("What are the inclusion criteria?", generic) == generic


def test_entity_gate_matches_nct_id_queries():
    """A question pinned to a specific trial must match on the NCT identifier itself."""
    pinned = [_make_passage(similarity=0.4, nct_id="NCT05794958")]
    kept = apply_entity_gate(
        "What bridging therapies does NCT05794958 permit?", pinned
    )
    assert kept == pinned


def test_extract_entity_terms_filters_scaffolding():
    """Scaffolding words must be excluded; clinical terms and NCT ids must survive."""
    terms = extract_entity_terms(
        "Which active protocols require a washout for prior checkpoint inhibitor therapy?"
    )
    assert "washout" in terms
    assert "checkpoint" in terms
    assert "inhibitor" in terms
    # Scaffolding must never be treated as a clinical subject.
    assert "protocols" not in terms
    assert "active" not in terms
    assert "prior" not in terms
