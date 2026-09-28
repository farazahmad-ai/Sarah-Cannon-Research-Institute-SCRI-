"""Automated Information Retrieval (IR) Evaluation Suite for SCRI Oncology Copilot.

Calculates:
- Recall@1: Target >= 60%
- Recall@3: Target >= 80%
- Recall@5 & Recall@10: Target >= 95%
- Mean Reciprocal Rank (MRR): Target >= 0.70
- Negative Refusal Accuracy: Target 100%
- Retrieval Latency: P50 & P95 (ms)

Saves results to:
1. backend/eval/reports/latest_report.json
2. backend/eval/reports/benchmark_report_<timestamp>.json
3. docs/eval-report.md (Executive Markdown Summary)
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows console encoding if needed
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.session import async_session_factory
from app.retrieval.hybrid import retrieve_protocols
from app.assistant.schemas import ProtocolPassage

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evaluator")

EVAL_DIR = Path(__file__).resolve().parent
REPORTS_DIR = EVAL_DIR / "reports"
ROOT_DIR = EVAL_DIR.parent.parent
GOLDEN_PATH = EVAL_DIR / "golden_dataset.json"
REPORT_MD_PATH = ROOT_DIR / "docs" / "eval-report.md"


def is_passage_match(
    passage: ProtocolPassage,
    target_nct: str | None,
    expected_section: str | None,
    target_keywords: list[str],
) -> bool:
    """Check if a retrieved passage satisfies the target clinical criterion."""
    if not target_nct:
        return False

    if passage.nct_id.upper() != target_nct.upper():
        return False

    # Check 1: exact or partial section match
    if expected_section and expected_section.lower() in passage.section_header.lower():
        return True

    # Check 2: all target keywords present in the text
    text_lower = passage.chunk_text.lower()
    if target_keywords and all(kw.lower() in text_lower for kw in target_keywords):
        return True

    return False


async def run_evaluation() -> dict:
    """Execute evaluation over all golden test cases."""
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(f"Golden dataset not found at {GOLDEN_PATH}")

    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    logger.info("Loaded %d test cases from %s", len(dataset), GOLDEN_PATH.name)

    results = []
    latencies = []
    positive_queries_count = 0
    negative_queries_count = 0
    reciprocal_ranks = []
    recall_at_1_hits = 0
    recall_at_3_hits = 0
    recall_at_5_hits = 0
    recall_at_10_hits = 0
    correct_refusals = 0

    for item in dataset:
        case_id = item["id"]
        category = item["category"]
        query = item["query"]
        target_nct = item.get("target_nct_id")
        expected_sec = item.get("expected_section")
        keywords = item.get("target_keywords", [])
        expected_refusal = item.get("expected_refusal", False)

        # If query specifies a target NCT ID, isolate retrieval to that trial (matching orchestrator behavior)
        nct_filter = target_nct if (target_nct and target_nct.upper() in query.upper()) else None

        start_t = time.perf_counter()
        async with async_session_factory() as session:
            passages = await retrieve_protocols(
                session,
                query,
                nct_id=nct_filter,
                limit=10,
                min_similarity=0.35,
            )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        latencies.append(elapsed_ms)

        query_result = {
            "id": case_id,
            "category": category,
            "query": query,
            "target_nct": target_nct,
            "expected_section": expected_sec,
            "expected_refusal": expected_refusal,
            "latency_ms": round(elapsed_ms, 2),
            "retrieved_count": len(passages),
            "matched_rank": None,
            "top_passages": [
                {
                    "rank": idx + 1,
                    "nct_id": p.nct_id,
                    "section": p.section_header,
                    "similarity": round(p.similarity, 3) if p.similarity else None,
                }
                for idx, p in enumerate(passages[:3])
            ],
        }

        if expected_refusal:
            negative_queries_count += 1
            # In negative control queries, passing entity gate should drop all irrelevant passages
            if len(passages) == 0:
                correct_refusals += 1
                query_result["success"] = True
            else:
                query_result["success"] = False
                query_result["failure_reason"] = (
                    f"Expected refusal (0 passages), but retrieved {len(passages)} passages"
                )
        else:
            positive_queries_count += 1
            matched_rank = None
            for idx, p in enumerate(passages, start=1):
                if is_passage_match(p, target_nct, expected_sec, keywords):
                    matched_rank = idx
                    break

            query_result["matched_rank"] = matched_rank

            if matched_rank is not None:
                reciprocal_ranks.append(1.0 / matched_rank)
                if matched_rank <= 1:
                    recall_at_1_hits += 1
                if matched_rank <= 3:
                    recall_at_3_hits += 1
                if matched_rank <= 5:
                    recall_at_5_hits += 1
                if matched_rank <= 10:
                    recall_at_10_hits += 1
                query_result["success"] = True
            else:
                reciprocal_ranks.append(0.0)
                query_result["success"] = False
                query_result["failure_reason"] = (
                    f"Target criteria '{expected_sec}' from {target_nct} not found in top 10 results"
                )

        results.append(query_result)

    # Compute aggregate statistics
    latencies.sort()
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p50_latency = latencies[len(latencies) // 2] if latencies else 0.0
    p95_idx = min(int(math.ceil(len(latencies) * 0.95)) - 1, len(latencies) - 1)
    p95_latency = latencies[p95_idx] if latencies else 0.0

    recall_1 = (recall_at_1_hits / positive_queries_count) if positive_queries_count else 0.0
    recall_3 = (recall_at_3_hits / positive_queries_count) if positive_queries_count else 0.0
    recall_5 = (recall_at_5_hits / positive_queries_count) if positive_queries_count else 0.0
    recall_10 = (recall_at_10_hits / positive_queries_count) if positive_queries_count else 0.0
    mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
    refusal_acc = (correct_refusals / negative_queries_count) if negative_queries_count else 1.0

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": len(dataset),
        "positive_test_cases": positive_queries_count,
        "negative_test_cases": negative_queries_count,
        "metrics": {
            "recall_at_1": round(recall_1, 4),
            "recall_at_3": round(recall_3, 4),
            "recall_at_5": round(recall_5, 4),
            "recall_at_10": round(recall_10, 4),
            "mrr": round(mrr, 4),
            "refusal_accuracy": round(refusal_acc, 4),
        },
        "targets": {
            "recall_at_1_target": 0.60,
            "recall_at_3_target": 0.80,
            "recall_at_5_target": 0.90,
            "recall_at_10_target": 0.95,
            "mrr_target": 0.70,
            "refusal_accuracy_target": 1.00,
        },
        "targets_met": {
            "recall_at_1": recall_1 >= 0.60,
            "recall_at_3": recall_3 >= 0.80,
            "recall_at_5": recall_5 >= 0.90,
            "recall_at_10": recall_10 >= 0.95,
            "mrr": mrr >= 0.70,
            "refusal_accuracy": refusal_acc >= 1.00,
        },
        "latency_ms": {
            "mean": round(mean_latency, 2),
            "p50": round(p50_latency, 2),
            "p95": round(p95_latency, 2),
        },
        "results": results,
    }

    return summary


def save_reports(summary: dict) -> tuple[Path, Path]:
    """Save structured JSON and human-readable Markdown reports."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Machine-readable JSON reports
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamped_file = REPORTS_DIR / f"benchmark_report_{ts_str}.json"
    latest_file = REPORTS_DIR / "latest_report.json"

    with open(timestamped_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # 2. Executive Markdown Report
    metrics = summary["metrics"]
    targets = summary["targets"]
    met = summary["targets_met"]
    lat = summary["latency_ms"]

    def _badge(passed: bool) -> str:
        return "✅ **PASS**" if passed else "❌ **FAIL**"

    md_content = f"""# SCRI Oncology Copilot — Retrieval & Grounding Evaluation Report

**Generated:** {summary["timestamp_utc"]}  
**Test Corpus:** 25 Landmark Clinical Trial Protocols across 5 Core Solid & Hematologic Tumor Types  
**Total Evaluation Cases:** {summary["total_test_cases"]} ({summary["positive_test_cases"]} Clinical Retrieval + {summary["negative_test_cases"]} Negative Refusals)

---

## 1. Executive Performance Scorecard

| Metric | Measured Value | Benchmark Target | Status | Clinical RAG Significance |
| :--- | :---: | :---: | :---: | :--- |
| **Recall@1 (Top-1 Accuracy)** | **{metrics["recall_at_1"] * 100:.1f}%** | &ge; 60.0% | {_badge(met["recall_at_1"])} | Exact protocol clause appears as the very first candidate. |
| **Recall@3** | **{metrics["recall_at_3"] * 100:.1f}%** | &ge; 80.0% | {_badge(met["recall_at_3"])} | Target criterion is retrieved within top 3 passages. |
| **Recall@5** | **{metrics["recall_at_5"] * 100:.1f}%** | &ge; 90.0% | {_badge(met["recall_at_5"])} | Target criterion is within primary LLM context window. |
| **Recall@10** | **{metrics["recall_at_10"] * 100:.1f}%** | &ge; 95.0% | {_badge(met["recall_at_10"])} | Global candidate pool coverage ceiling. |
| **Mean Reciprocal Rank (MRR)** | **{metrics["mrr"]:.3f}** | &ge; 0.700 | {_badge(met["mrr"])} | Average reciprocal rank (1 / rank) across positive clinical queries. |
| **Negative Refusal Accuracy** | **{metrics["refusal_accuracy"] * 100:.1f}%** | 100.0% | {_badge(met["refusal_accuracy"])} | Entity gate successfully blocks off-corpus / non-existent trial queries. |

---

## 2. Latency Benchmarks (Hybrid Search Pipeline)

*Includes OpenAI `text-embedding-3-small` generation + pgvector Cosine Search + PostgreSQL Full-Text Search (GIN `to_tsvector`) + Reciprocal Rank Fusion (RRF).*

| Percentile | Latency (ms) | Target | Clinical User Experience |
| :--- | :---: | :---: | :--- |
| **P50 (Median)** | **{lat["p50"]} ms** | < 400 ms | Sub-second responsiveness for busy coordinators. |
| **P95** | **{lat["p95"]} ms** | < 800 ms | High reliability even during cold queries. |
| **Mean Latency** | **{lat["mean"]} ms** | < 500 ms | Predictable pipeline performance. |

---

## 3. Per-Query Breakdown & Retrieval Analysis

| ID | Disease Category | Target Trial | Expected Section / Topic | Rank | Latency | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
"""

    for r in summary["results"]:
        rank_str = f"#{r['matched_rank']}" if r["matched_rank"] is not None else ("N/A (Refusal)" if r["expected_refusal"] else "Miss")
        status_str = "✅ PASS" if r["success"] else "❌ FAIL"
        target_trial = r["target_nct"] or "Off-Corpus Control"
        exp_sec = r["expected_section"] or "Deterministic Refusal"
        md_content += f"| `{r['id']}` | {r['category']} | `{target_trial}` | {exp_sec} | {rank_str} | {r['latency_ms']} ms | {status_str} |\n"

    md_content += """
---

## 4. Methodology & Evaluation Philosophy

1. **Strict Oncology Standard:** A clinical coordinator cannot afford to have a crucial exclusion criterion (e.g. *Platelets < 100,000* or *Prior anti-cancer treatment within 4 weeks*) buried on page 10. `Recall@3` guarantees the evidence is immediately available in the prompt.
2. **Negative Control Defense (Zero Hallucination):** Negative controls (e.g. pediatric leukemia or non-existent NCT IDs) are tested against our clinical entity gate. Retrieval must abstain completely (0 passages) so the LLM cannot hallucinate from pre-trained priors.
3. **Reproducibility:** This benchmark can be re-run at any time via:
   ```bash
   uv run python eval/evaluate_retrieval.py
   ```
"""

    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)

    return latest_file, REPORT_MD_PATH


def print_scorecard(summary: dict) -> None:
    """Print an executive ASCII scorecard in the terminal."""
    m = summary["metrics"]
    t = summary["targets"]
    lat = summary["latency_ms"]

    def _mark(passed: bool) -> str:
        return "[PASS]" if passed else "[FAIL]"

    print("\n" + "=" * 70)
    print("        SCRI ONCOLOGY COPILOT - RETRIEVAL EVALUATION SCORECARD")
    print("=" * 70)
    print(f"Total Test Cases : {summary['total_test_cases']} ({summary['positive_test_cases']} positive, {summary['negative_test_cases']} negative)")
    print("-" * 70)
    print(f"Recall@1 (Top-1)  : {m['recall_at_1'] * 100:6.1f}%  (Target: >= {t['recall_at_1_target'] * 100:.0f}%)  {_mark(summary['targets_met']['recall_at_1'])}")
    print(f"Recall@3          : {m['recall_at_3'] * 100:6.1f}%  (Target: >= {t['recall_at_3_target'] * 100:.0f}%)  {_mark(summary['targets_met']['recall_at_3'])}")
    print(f"Recall@5          : {m['recall_at_5'] * 100:6.1f}%  (Target: >= {t['recall_at_5_target'] * 100:.0f}%)  {_mark(summary['targets_met']['recall_at_5'])}")
    print(f"Recall@10         : {m['recall_at_10'] * 100:6.1f}%  (Target: >= {t['recall_at_10_target'] * 100:.0f}%)  {_mark(summary['targets_met']['recall_at_10'])}")
    print(f"Mean Recip. Rank  : {m['mrr']:6.3f}   (Target: >= {t['mrr_target']:.2f})   {_mark(summary['targets_met']['mrr'])}")
    print(f"Refusal Accuracy  : {m['refusal_accuracy'] * 100:6.1f}%  (Target: == 100%) {_mark(summary['targets_met']['refusal_accuracy'])}")
    print("-" * 70)
    print(f"Latency P50       : {lat['p50']:6.1f} ms")
    print(f"Latency P95       : {lat['p95']:6.1f} ms")
    print(f"Latency Mean      : {lat['mean']:6.1f} ms")
    print("=" * 70 + "\n")


async def main():
    summary = await run_evaluation()
    json_path, md_path = save_reports(summary)
    print_scorecard(summary)
    logger.info("JSON report saved to: %s", json_path)
    logger.info("Markdown report saved to: %s", md_path)


if __name__ == "__main__":
    asyncio.run(main())
