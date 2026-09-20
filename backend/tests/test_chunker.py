"""Corpus invariant tests for protocol chunker over the 25 landmark trials.

These tests run completely offline without database or network dependencies.
They enforce structural invariants that prevent regressions like D-1 (exclusion
mislabeling) and D-2 (numbered-list collapse).
"""

import json
from pathlib import Path
from app.ingest.chunker import chunk_protocol, load_trial_json

_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
_DOWNLOADS_DIR = _WORKSPACE_ROOT / "data" / "downloads"
_MANIFEST_PATH = _DOWNLOADS_DIR / "manifest.json"


def _load_all_trials():
    """Load and chunk all 25 landmark trials from the local downloads directory."""
    assert _MANIFEST_PATH.exists(), f"Manifest not found at {_MANIFEST_PATH}"
    with open(_MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    trials_with_chunks = []
    for entry in manifest["studies"]:
        nct_id = entry["nct_id"]
        json_path = _DOWNLOADS_DIR / entry["local_json_path"]
        assert json_path.exists(), f"Trial JSON missing: {json_path}"

        trial = load_trial_json(json_path)
        trial.category = entry["category"]
        chunks = chunk_protocol(trial)
        trials_with_chunks.append((trial, chunks))

    return trials_with_chunks


def test_corpus_total_chunk_count():
    """Total chunks across all 25 landmark trials must be exactly 563."""
    trials_with_chunks = _load_all_trials()
    assert len(trials_with_chunks) == 25

    total_chunks = sum(len(chunks) for _, chunks in trials_with_chunks)
    assert total_chunks == 563, f"Expected 563 total chunks, got {total_chunks}"


def test_every_trial_has_exactly_one_brief_summary():
    """Every trial must produce exactly 1 BRIEF_SUMMARY chunk."""
    trials_with_chunks = _load_all_trials()

    for trial, chunks in trials_with_chunks:
        summaries = [c for c in chunks if c.section_type == "BRIEF_SUMMARY"]
        assert len(summaries) == 1, (
            f"{trial.nct_id} expected exactly 1 BRIEF_SUMMARY, got {len(summaries)}"
        )


def test_exclusion_chunk_presence_and_header():
    """Trials with exclusion criteria must produce ELIGIBILITY_EXCLUSION chunks.

    Specifically guards against D-1 regression where exclusion sections were
    mislabeled as inclusion criteria.
    """
    trials_with_chunks = _load_all_trials()

    # Landmark trials confirmed to have exclusion criteria in protocol text
    trials_requiring_exclusions = {
        "NCT07172802": 6,   # Key Exclusion Criteria
        "NCT07297667": 17,  # Key Exclusion Criteria
        "NCT07365319": 6,   # Key exclusion criteria:
        "NCT07468071": 4,   # Key Exclusion Criteria
        "NCT06172478": 11,  # Exclusion criteria (no colon)
    }

    for trial, chunks in trials_with_chunks:
        if trial.nct_id in trials_requiring_exclusions:
            expected_min = trials_requiring_exclusions[trial.nct_id]
            exclusions = [c for c in chunks if c.section_type == "ELIGIBILITY_EXCLUSION"]
            assert len(exclusions) >= expected_min, (
                f"{trial.nct_id} expected at least {expected_min} exclusion chunks, got {len(exclusions)}"
            )
            # Verify section_header is branded as Exclusion
            for exc in exclusions:
                assert "Exclusion" in exc.section_header, (
                    f"{trial.nct_id} exclusion chunk has bad header: {exc.section_header}"
                )


def test_numbered_list_parsing():
    """Numbered lists (1. or 1)) must split into individual atomic chunks.

    Specifically guards against D-2 regression where numbered criteria
    collapsed into a single giant chunk.
    """
    trials_with_chunks = _load_all_trials()

    # Trials with numbered criteria that previously collapsed
    numbered_trials = {
        "NCT04002947": 20,  # 1. style
        "NCT07606963": 25,  # 1. style
        "NCT06906822": 30,  # 1. style
    }

    for trial, chunks in trials_with_chunks:
        if trial.nct_id in numbered_trials:
            min_chunks = numbered_trials[trial.nct_id]
            assert len(chunks) >= min_chunks, (
                f"{trial.nct_id} expected at least {min_chunks} chunks, got {len(chunks)}"
            )


def test_token_ceiling_and_non_empty_content():
    """All chunks must have non-empty headers and text, and respect max token limit."""
    trials_with_chunks = _load_all_trials()

    for trial, chunks in trials_with_chunks:
        for chunk in chunks:
            assert chunk.section_header.strip(), f"{trial.nct_id} chunk has empty header"
            assert chunk.chunk_text.strip(), f"{trial.nct_id} chunk has empty text"
            assert chunk.token_count <= 1600, (
                f"{trial.nct_id} chunk [{chunk.section_header}] exceeds 1600 tokens: {chunk.token_count}"
            )


def test_chunk_index_uniqueness_per_trial():
    """Chunk indices must be contiguous and unique per trial."""
    trials_with_chunks = _load_all_trials()

    for trial, chunks in trials_with_chunks:
        indices = [c.chunk_index for c in chunks]
        assert len(indices) == len(set(indices)), (
            f"{trial.nct_id} has duplicate chunk indices: {indices}"
        )
        assert indices == list(range(len(chunks))), (
            f"{trial.nct_id} chunk indices are not contiguous from 0: {indices}"
        )
