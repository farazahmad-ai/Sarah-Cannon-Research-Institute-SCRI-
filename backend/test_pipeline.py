"""SCRI Oncology Copilot - Terminal Pipeline & Workflow Harness.

This standalone test harness demonstrates the complete end-to-end query processing
pipeline of the SCRI Oncology Copilot in the terminal:
1. Environment & Database Configuration
2. Query Parsing & Clinical Entity Extraction
3. Dense Vector Search (OpenAI embeddings + pgvector cosine similarity)
4. Lexical Full-Text Search (PostgreSQL websearch_to_tsquery)
5. Reciprocal Rank Fusion (RRF k=60 combining vector & FTS)
6. Similarity Floor & Clinical Entity Gate Filtering
7. Evidence Gate Check (Deterministic Zero-Evidence Refusal if off-corpus)
8. Context Injection & PydanticAI Agent Generation (GPT-4o streaming)
9. Grounding & Citation Verification (Sanitizing ungrounded references)
10. Final Verification & Pipeline Recap
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors for terminal clarity
class Style:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner(step_num: int, title: str) -> None:
    print(f"\n{Style.BOLD}{Style.CYAN}{'=' * 75}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}[STEP {step_num}] {title}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}{'=' * 75}{Style.RESET}")


async def run_pipeline(query: str, disease_category: str | None = None) -> None:
    start_total_time = time.perf_counter()

    # -------------------------------------------------------------------------
    # STEP 1: CONFIGURATION & ENVIRONMENT
    # -------------------------------------------------------------------------
    print_banner(1, "Environment & Database Configuration")
    from app.config import settings
    from app.database.session import async_session_factory
    from app.database.trials import get_corpus_manifest

    print(f"{Style.BOLD}App Name:{Style.RESET}          {settings.APP_NAME}")
    print(f"{Style.BOLD}Environment:{Style.RESET}       {settings.ENVIRONMENT}")
    print(f"{Style.BOLD}Chat LLM Model:{Style.RESET}    {settings.OPENAI_CHAT_MODEL}")
    print(f"{Style.BOLD}Embedding Model:{Style.RESET}   {settings.OPENAI_EMBEDDING_MODEL} ({settings.OPENAI_EMBEDDING_DIMENSIONS} dims)")
    print(f"{Style.BOLD}Gateway / URL:{Style.RESET}     {settings.effective_base_url or 'Default OpenAI'}")
    print(f"{Style.BOLD}Supabase Host:{Style.RESET}     {settings.SUPABASE_URL}")

    async with async_session_factory() as session:
        manifest = await get_corpus_manifest(session)
        total_trials = sum(manifest.values())
        print(f"\n{Style.GREEN}[OK] Connected to Database successfully!{Style.RESET}")
        print(f"{Style.BOLD}Active Trial Corpus ({total_trials} total trials across categories):{Style.RESET}")
        for cat, count in sorted(manifest.items()):
            print(f"  * {cat.replace('_', ' ').title():<32} : {count} trial(s)")

    # -------------------------------------------------------------------------
    # STEP 2: QUERY INPUT & CLINICAL ENTITY ANALYSIS
    # -------------------------------------------------------------------------
    print_banner(2, "Query Input & Clinical Entity Extraction")
    from app.retrieval.hybrid import _query_nct_ids, extract_entity_terms

    print(f"{Style.BOLD}Incoming Query:{Style.RESET} \"{Style.YELLOW}{query}{Style.RESET}\"")
    if disease_category:
        print(f"{Style.BOLD}Disease Filter:{Style.RESET} {disease_category}")

    entity_terms = extract_entity_terms(query)
    pinned_ncts = _query_nct_ids(query)

    print(f"\n{Style.BOLD}Clinical Entity Gate Analysis (Audit C3):{Style.RESET}")
    print(f"  * Extracted Specific Terms : {sorted(list(entity_terms)) if entity_terms else '[None found]'}")
    print(f"  * Pinned Trial NCT IDs     : {sorted(list(pinned_ncts)) if pinned_ncts else '[None]'}")
    print(f"  * Explanation              : Non-clinical scaffolding words (e.g. 'what', 'criteria', 'trial')")
    print(f"                               are filtered out so similarity is evaluated on true medical terms.")

    # -------------------------------------------------------------------------
    # STEP 3: DENSE VECTOR SEARCH (pgvector)
    # -------------------------------------------------------------------------
    print_banner(3, "Dense Vector Search (OpenAI Embeddings + pgvector)")
    from app.retrieval.vector_search import VECTOR_TOP_K, vector_search

    print(f"Generating 1536-dim embedding for query and querying pgvector (top {VECTOR_TOP_K})...")
    t0 = time.perf_counter()
    async with async_session_factory() as session:
        vector_passages = await vector_search(
            session,
            query,
            disease_category=disease_category,
            limit=VECTOR_TOP_K,
        )
    vec_time = time.perf_counter() - t0
    print(f"{Style.GREEN}[OK] Vector search completed in {vec_time:.2f}s ({len(vector_passages)} chunks retrieved){Style.RESET}\n")

    print(f"{Style.BOLD}Top 5 Vector Candidates (by Cosine Similarity):{Style.RESET}")
    for idx, p in enumerate(vector_passages[:5], start=1):
        sim = f"{p.similarity:.4f}" if p.similarity is not None else "N/A"
        preview = (p.chunk_text[:110] + "...").replace("\n", " ")
        print(f"  [{idx}] {Style.BOLD}{p.nct_id}{Style.RESET} | Sim: {Style.CYAN}{sim}{Style.RESET} | {p.section_header}")
        print(f"      {Style.DIM}{preview}{Style.RESET}")

    # -------------------------------------------------------------------------
    # STEP 4: LEXICAL FULL-TEXT SEARCH (PostgreSQL FTS)
    # -------------------------------------------------------------------------
    print_banner(4, "Lexical Full-Text Search (PostgreSQL websearch_to_tsquery)")
    from app.retrieval.fts_search import FTS_TOP_K, fts_search

    print(f"Converting query to tsquery and executing full-text search (top {FTS_TOP_K})...")
    t0 = time.perf_counter()
    async with async_session_factory() as session:
        fts_passages = await fts_search(
            session,
            query,
            disease_category=disease_category,
            limit=FTS_TOP_K,
        )
    fts_time = time.perf_counter() - t0
    print(f"{Style.GREEN}[OK] FTS search completed in {fts_time:.2f}s ({len(fts_passages)} chunks matched){Style.RESET}\n")

    print(f"{Style.BOLD}Top 5 Lexical Candidates (by ts_rank_cd):{Style.RESET}")
    for idx, p in enumerate(fts_passages[:5], start=1):
        preview = (p.chunk_text[:110] + "...").replace("\n", " ")
        print(f"  [{idx}] {Style.BOLD}{p.nct_id}{Style.RESET} | {p.section_header}")
        print(f"      {Style.DIM}{preview}{Style.RESET}")

    # -------------------------------------------------------------------------
    # STEP 5: RECIPROCAL RANK FUSION (RRF)
    # -------------------------------------------------------------------------
    print_banner(5, "Reciprocal Rank Fusion (RRF k=60)")
    from app.retrieval.rrf import RRF_K, reciprocal_rank_fusion

    passages_by_id = {p.chunk_id: p for p in (vector_passages + fts_passages)}
    ranked_lists = [
        [p.chunk_id for p in vector_passages],
        [p.chunk_id for p in fts_passages],
    ]
    fused_ranked = reciprocal_rank_fusion(ranked_lists, k=RRF_K)

    print(f"Fused {len(ranked_lists[0])} vector chunks and {len(ranked_lists[1])} FTS chunks into {len(fused_ranked)} unique candidates.")
    print(f"Formula: score(c) = SUM [ 1 / (60 + rank_source) ]\n")

    # Map rank positions for display
    vec_rank_map = {cid: r + 1 for r, cid in enumerate(ranked_lists[0])}
    fts_rank_map = {cid: r + 1 for r, cid in enumerate(ranked_lists[1])}

    print(f"{Style.BOLD}Top 5 Fused Candidates:{Style.RESET}")
    candidates = []
    for idx, (chunk_id, fused_score) in enumerate(fused_ranked[:5], start=1):
        p = passages_by_id[chunk_id]
        v_rank = vec_rank_map.get(chunk_id, "-")
        f_rank = fts_rank_map.get(chunk_id, "-")
        print(f"  [{idx}] {Style.BOLD}{p.nct_id}{Style.RESET} | RRF Score: {Style.YELLOW}{fused_score:.5f}{Style.RESET} (Vec Rank: {v_rank}, FTS Rank: {f_rank})")
        print(f"      Section: {p.section_header}")

    for chunk_id, _ in fused_ranked:
        if chunk_id in passages_by_id:
            candidates.append(passages_by_id[chunk_id])

    # -------------------------------------------------------------------------
    # STEP 6: FILTERING - SIMILARITY FLOOR & CLINICAL ENTITY GATE
    # -------------------------------------------------------------------------
    print_banner(6, "Filtering: Similarity Floor & Clinical Entity Gate")
    from app.retrieval.hybrid import (
        DEFAULT_MIN_SIMILARITY,
        _count_matching_terms,
        apply_entity_gate,
        apply_similarity_floor,
    )

    print(f"1. Applying Cosine Similarity Floor (floor >= {DEFAULT_MIN_SIMILARITY}):")
    floored_passages = apply_similarity_floor(
        candidates,
        DEFAULT_MIN_SIMILARITY,
        vector_search_healthy=True,
        preserve_top_lexical=2,
    )
    print(f"   Passages before floor: {len(candidates)} -> After floor: {len(floored_passages)}")

    print(f"\n2. Applying Clinical Entity Relevance Gate (requires >= 2 term matches or NCT match):")
    gated_passages = apply_entity_gate(query, floored_passages)
    print(f"   Passages before entity gate: {len(floored_passages)} -> After entity gate: {len(gated_passages)}")

    if gated_passages:
        print(f"\n{Style.BOLD}Sample Entity Overlap Diagnostics on Top Candidates:{Style.RESET}")
        for p in gated_passages[:3]:
            matches = _count_matching_terms(p, entity_terms)
            print(f"   * {p.nct_id} ({p.section_header[:40]}...) : Matched {matches} clinical terms")

    final_passages = gated_passages[:12]

    # -------------------------------------------------------------------------
    # STEP 7: EVIDENCE GATE CHECK (Audit Finding C3)
    # -------------------------------------------------------------------------
    print_banner(7, "Minimum Evidence Gate Check")
    from app.assistant.prompts import build_no_evidence_refusal

    if not final_passages:
        print(f"{Style.RED}{Style.BOLD}[REFUSAL] ZERO EVIDENCE RETRIEVED!{Style.RESET}")
        print(f"In oncology, empty context MUST NOT fall back to general LLM training knowledge.")
        print(f"The system generates a deterministic, zero-token refusal response:\n")
        refusal = build_no_evidence_refusal(query, manifest)
        print(f"{Style.YELLOW}{refusal}{Style.RESET}")
        print(f"\n{Style.BOLD}Execution safely completed via deterministic guardrail.{Style.RESET}")
        return

    print(f"{Style.GREEN}[OK] Evidence Gate Passed! {len(final_passages)} grounded passages ready for LLM context.{Style.RESET}")

    # -------------------------------------------------------------------------
    # STEP 8: PROMPT ASSEMBLY & PYDANTICAI AGENT STREAMING
    # -------------------------------------------------------------------------
    print_banner(8, "Prompt Context Assembly & PydanticAI Streaming")
    from app.assistant.agent import oncology_agent
    from app.assistant.deps import OncologyAgentDeps
    from app.assistant.prompts import format_protocol_context

    print(f"{Style.BOLD}Context Preview injected into LLM System Prompt:{Style.RESET}")
    context_preview = format_protocol_context(final_passages[:2])
    print(f"{Style.DIM}{context_preview[:400]}...\n[... truncated {len(final_passages)-2} more passages ...]{Style.RESET}\n")

    deps = OncologyAgentDeps(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        retrieved_passages=final_passages,
        corpus_manifest=manifest,
    )

    print(f"{Style.BOLD}Streaming Assistant Answer from GPT-4o in real-time:{Style.RESET}\n")
    print(f"{Style.CYAN}{'-' * 75}{Style.RESET}")

    collected_tokens = []
    t_llm_start = time.perf_counter()
    async with oncology_agent.run_stream(query, deps=deps) as result:
        async for delta in result.stream_text(delta=True):
            if delta:
                collected_tokens.append(delta)
                sys.stdout.write(delta)
                sys.stdout.flush()
    t_llm_end = time.perf_counter()

    full_answer = "".join(collected_tokens)
    print(f"\n{Style.CYAN}{'-' * 75}{Style.RESET}")
    print(f"{Style.GREEN}[OK] Completed streaming in {t_llm_end - t_llm_start:.2f}s ({len(full_answer)} characters){Style.RESET}")

    # -------------------------------------------------------------------------
    # STEP 9: GROUNDING & CITATION VALIDATION
    # -------------------------------------------------------------------------
    print_banner(9, "Grounding & Citation Validation")
    from app.grounding.validator import GroundingValidator

    parsed_citations = GroundingValidator.parse_citations(full_answer)
    verified_citations = GroundingValidator.validate_citations(full_answer, final_passages)
    sanitized_answer = GroundingValidator.sanitize_unverified_citations(full_answer, final_passages)

    print(f"Total citations detected in response text : {len(parsed_citations)}")
    print(f"Verified against retrieved passages      : {len(verified_citations)}")

    print(f"\n{Style.BOLD}Citation Verification Breakdown:{Style.RESET}")
    for idx, c in enumerate(verified_citations, start=1):
        print(f"  [{idx}] {Style.GREEN}[VALID]{Style.RESET} : {Style.BOLD}{c.nct_id}{Style.RESET} | {c.section_header}")
        print(f"      Quote snippet: {Style.DIM}\"{c.verbatim_quote[:90]}...\"{Style.RESET}")

    if len(parsed_citations) > len(verified_citations):
        print(f"\n{Style.RED}[WARNING] Ungrounded citations were stripped/sanitized!{Style.RESET}")
    else:
        print(f"\n{Style.GREEN}[OK] 100% of generated citations strictly grounded in retrieved evidence!{Style.RESET}")

    # -------------------------------------------------------------------------
    # STEP 10: RECAP & METRICS
    # -------------------------------------------------------------------------
    print_banner(10, "Pipeline Execution Recap")
    total_time = time.perf_counter() - start_total_time
    print(f"* Total Pipeline Wall-Clock Time : {total_time:.2f}s")
    print(f"* Vector Search Time            : {vec_time:.2f}s")
    print(f"* FTS Search Time               : {fts_time:.2f}s")
    print(f"* LLM Generation Time           : {t_llm_end - t_llm_start:.2f}s")
    print(f"* Candidate Chunks Examined     : {len(candidates)}")
    print(f"* Passages Passed to LLM        : {len(final_passages)}")
    print(f"* Verified Protocol Citations   : {len(verified_citations)}")
    print(f"{Style.BOLD}{Style.GREEN}=== HARNESS RUN SUCCESSFUL ==={Style.RESET}\n")


def print_menu() -> None:
    print(f"\n{Style.BOLD}{Style.CYAN}SCRI Oncology Copilot - Pipeline Test Harness{Style.RESET}")
    print("Choose a test query mode:")
    print("  1. Standard On-Corpus Question (Lung Cancer & Brain Metastases criteria)")
    print("  2. Targeted Biomarker Question (KRAS G12D inhibitor trial VS-7375)")
    print("  3. Off-Corpus Abstention Test (Pediatric Glioblastoma - tests Zero-Hallucination Gate)")
    print("  4. Custom Query (Type your own question)")
    print("  5. Exit")


async def main() -> None:
    if len(sys.argv) > 1:
        # Direct CLI argument passed
        custom_query = " ".join(sys.argv[1:])
        await run_pipeline(custom_query)
        return

    while True:
        print_menu()
        choice = input(f"\n{Style.BOLD}Select an option (1-5) [default 1]: {Style.RESET}").strip()
        if choice == "" or choice == "1":
            await run_pipeline("What are the exclusion criteria regarding brain metastases in non-small cell lung cancer trials?")
            break
        elif choice == "2":
            await run_pipeline("What prior therapies are permitted or excluded for patients in the KRAS G12D trial NCT07659782?")
            break
        elif choice == "3":
            await run_pipeline("What are the inclusion criteria for pediatric glioblastoma protocols?")
            break
        elif choice == "4":
            custom_query = input(f"{Style.BOLD}Enter your oncology screening question: {Style.RESET}").strip()
            if custom_query:
                await run_pipeline(custom_query)
            else:
                print("No query entered.")
            break
        elif choice == "5" or choice.lower() in ("q", "exit"):
            print("Exiting.")
            break
        else:
            print("Invalid choice, please select 1-5.")


if __name__ == "__main__":
    asyncio.run(main())
