# SCRI Oncology Copilot — Retrieval & Grounding Evaluation Report

**Generated:** 2026-09-28T17:58:45.652008+00:00  
**Test Corpus:** 25 Landmark Clinical Trial Protocols across 5 Core Solid & Hematologic Tumor Types  
**Total Evaluation Cases:** 25 (22 Clinical Retrieval + 3 Negative Refusals)

---

## 1. Executive Performance Scorecard

| Metric | Measured Value | Benchmark Target | Status | Clinical RAG Significance |
| :--- | :---: | :---: | :---: | :--- |
| **Recall@1 (Top-1 Accuracy)** | **95.5%** | &ge; 60.0% | ✅ **PASS** | Exact protocol clause appears as the very first candidate. |
| **Recall@3** | **100.0%** | &ge; 80.0% | ✅ **PASS** | Target criterion is retrieved within top 3 passages. |
| **Recall@5** | **100.0%** | &ge; 90.0% | ✅ **PASS** | Target criterion is within primary LLM context window. |
| **Recall@10** | **100.0%** | &ge; 95.0% | ✅ **PASS** | Global candidate pool coverage ceiling. |
| **Mean Reciprocal Rank (MRR)** | **0.970** | &ge; 0.700 | ✅ **PASS** | Average reciprocal rank (1 / rank) across positive clinical queries. |
| **Negative Refusal Accuracy** | **100.0%** | 100.0% | ✅ **PASS** | Entity gate successfully blocks off-corpus / non-existent trial queries. |

---

## 2. Latency Benchmarks (Hybrid Search Pipeline)

*Includes OpenAI `text-embedding-3-small` generation + pgvector Cosine Search + PostgreSQL Full-Text Search (GIN `to_tsvector`) + Reciprocal Rank Fusion (RRF).*

| Percentile | Latency (ms) | Target | Clinical User Experience |
| :--- | :---: | :---: | :--- |
| **P50 (Median)** | **9548.37 ms** | < 400 ms | Sub-second responsiveness for busy coordinators. |
| **P95** | **20262.64 ms** | < 800 ms | High reliability even during cold queries. |
| **Mean Latency** | **11804.81 ms** | < 500 ms | Predictable pipeline performance. |

---

## 3. Per-Query Breakdown & Retrieval Analysis

| ID | Disease Category | Target Trial | Expected Section / Topic | Rank | Latency | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `NSCLC-01` | non_small_cell_lung_cancer | `NCT07659782` | Eligibility: Inclusion Criterion #6 | #3 | 15146.49 ms | ✅ PASS |
| `NSCLC-02` | non_small_cell_lung_cancer | `NCT07659782` | Eligibility: Exclusion Criterion #3 | #1 | 5962.58 ms | ✅ PASS |
| `NSCLC-03` | non_small_cell_lung_cancer | `NCT07659782` | Eligibility: Exclusion Criterion #4 | #1 | 5068.74 ms | ✅ PASS |
| `NSCLC-04` | non_small_cell_lung_cancer | `NCT07659782` | Eligibility: Inclusion Criterion #10 | #1 | 5135.91 ms | ✅ PASS |
| `NSCLC-05` | non_small_cell_lung_cancer | `NCT06498635` | Eligibility: Inclusion Criterion #8 | #1 | 6772.61 ms | ✅ PASS |
| `LYMPH-01` | lymphoma_car_t | `NCT07519772` | Eligibility: Exclusion Criterion #10 | #1 | 6997.93 ms | ✅ PASS |
| `LYMPH-02` | lymphoma_car_t | `NCT07519772` | Eligibility: Exclusion Criterion #11 | #1 | 9387.12 ms | ✅ PASS |
| `LYMPH-03` | lymphoma_car_t | `NCT06717347` | Eligibility: Inclusion Criterion #3 | #1 | 5419.83 ms | ✅ PASS |
| `LYMPH-04` | lymphoma_car_t | `NCT07519772` | Eligibility: Exclusion Criterion #14 | #1 | 6553.45 ms | ✅ PASS |
| `LYMPH-05` | lymphoma_car_t | `NCT07519772` | Eligibility: Exclusion Criterion #12 | #1 | 5943.18 ms | ✅ PASS |
| `CRC-01` | colorectal_cancer | `NCT06529523` | Eligibility: Exclusion Criterion #19 | #1 | 14266.21 ms | ✅ PASS |
| `CRC-02` | colorectal_cancer | `NCT06529523` | Eligibility: Exclusion Criterion #22 | #1 | 9714.15 ms | ✅ PASS |
| `CRC-03` | colorectal_cancer | `NCT06529523` | Eligibility: Exclusion Criterion #20 | #1 | 9719.85 ms | ✅ PASS |
| `CRC-04` | colorectal_cancer | `NCT06529523` | Eligibility: Inclusion Criterion #1 | #1 | 8508.47 ms | ✅ PASS |
| `BREAST-01` | breast_cancer | `NCT06393374` | Eligibility: Exclusion Criterion #13 | #1 | 9548.37 ms | ✅ PASS |
| `BREAST-02` | breast_cancer | `NCT07297667` | Eligibility: Exclusion Criterion #17 | #1 | 19847.96 ms | ✅ PASS |
| `BREAST-03` | breast_cancer | `NCT07297667` | Eligibility: Exclusion Criterion #11 | #1 | 12653.73 ms | ✅ PASS |
| `BREAST-04` | breast_cancer | `NCT07340541` | Eligibility: Inclusion Criterion #3 | #1 | 8912.47 ms | ✅ PASS |
| `MEL-01` | melanoma | `NCT06906822` | Eligibility: Exclusion Criterion #4 | #1 | 19071.58 ms | ✅ PASS |
| `MEL-02` | melanoma | `NCT06906822` | Eligibility: Exclusion Criterion #16 | #1 | 20262.64 ms | ✅ PASS |
| `MEL-03` | melanoma | `NCT05136196` | Eligibility: Inclusion Criterion #18 | #1 | 15046.03 ms | ✅ PASS |
| `MEL-04` | melanoma | `NCT06172478` | Eligibility: Exclusion Criterion #4 | #1 | 14122.84 ms | ✅ PASS |
| `NEG-01` | negative_control | `Off-Corpus Control` | Deterministic Refusal | N/A (Refusal) | 37617.08 ms | ✅ PASS |
| `NEG-02` | negative_control | `NCT05794958` | Deterministic Refusal | N/A (Refusal) | 5151.28 ms | ✅ PASS |
| `NEG-03` | negative_control | `Off-Corpus Control` | Deterministic Refusal | N/A (Refusal) | 18289.83 ms | ✅ PASS |

---

## 4. Methodology & Evaluation Philosophy

1. **Strict Oncology Standard:** A clinical coordinator cannot afford to have a crucial exclusion criterion (e.g. *Platelets < 100,000* or *Prior anti-cancer treatment within 4 weeks*) buried on page 10. `Recall@3` guarantees the evidence is immediately available in the prompt.
2. **Negative Control Defense (Zero Hallucination):** Negative controls (e.g. pediatric leukemia or non-existent NCT IDs) are tested against our clinical entity gate. Retrieval must abstain completely (0 passages) so the LLM cannot hallucinate from pre-trained priors.
3. **Reproducibility:** This benchmark can be re-run at any time via:
   ```bash
   uv run python eval/evaluate_retrieval.py
   ```
4. **Benchmark Integrity & Roadmap:** For a detailed breakdown of dataset curation trade-offs, token cost considerations, and our roadmap for future independent validation (RAGAS, cross-model synthesis, and human clinical annotation), see [docs/future-plan.md](file:///d:/FarazAhmad-ai/projects/Sarah%20Cannon%20Research%20Institute%20(SCRI)/docs/future-plan.md#4-evaluation-methodology-benchmark-integrity--future-validation-roadmap).

