"""Regression guard tests for the Information Retrieval (IR) benchmark suite.

Validates that hybrid retrieval (pgvector + FTS + RRF + entity gate) meets
the target metrics on the 25-case golden dataset:
- Recall@1 >= 60%
- Recall@3 >= 80%
- Recall@5 >= 90%
- Recall@10 >= 95%
- MRR >= 0.70
- Refusal Accuracy == 100%
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from app.database.session import engine

REPORT_PATH = Path(__file__).resolve().parent.parent / "eval" / "reports" / "latest_report.json"


def test_latest_evaluation_report_meets_slas():
    """Verify that the generated benchmark report satisfies all clinical IR targets."""
    assert REPORT_PATH.exists(), f"Benchmark report not found at {REPORT_PATH}. Run eval/evaluate_retrieval.py first."
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    metrics = data["metrics"]
    assert metrics["recall_at_1"] >= 0.60, f"Recall@1 too low: {metrics['recall_at_1']:.1%}"
    assert metrics["recall_at_3"] >= 0.80, f"Recall@3 too low: {metrics['recall_at_3']:.1%}"
    assert metrics["recall_at_5"] >= 0.90, f"Recall@5 too low: {metrics['recall_at_5']:.1%}"
    assert metrics["recall_at_10"] >= 0.95, f"Recall@10 too low: {metrics['recall_at_10']:.1%}"
    assert metrics["mrr"] >= 0.70, f"MRR too low: {metrics['mrr']:.3f}"
    assert metrics["refusal_accuracy"] >= 0.99, f"Refusal accuracy failed: {metrics['refusal_accuracy']:.1%}"


@pytest.fixture
async def cleanup_db_pool():
    yield
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.anyio
async def test_live_golden_dataset_retrieval(cleanup_db_pool):
    """Live integration run of evaluation suite against Supabase & embedding API."""
    from eval.evaluate_retrieval import run_evaluation

    report = await run_evaluation()
    metrics = report["metrics"]

    assert metrics["recall_at_1"] >= 0.60, f"Recall@1 too low: {metrics['recall_at_1']:.1%}"
    assert metrics["recall_at_3"] >= 0.80, f"Recall@3 too low: {metrics['recall_at_3']:.1%}"
    assert metrics["mrr"] >= 0.70, f"MRR too low: {metrics['mrr']:.3f}"
    assert metrics["refusal_accuracy"] >= 0.99, f"Refusal accuracy failed: {metrics['refusal_accuracy']:.1%}"
