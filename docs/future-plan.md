# SCRI Oncology Copilot — Multi-Turn Architecture & Future Scaling Plan

> **Scope Note:** This document records the architectural analysis, known limitations, and deliberate trade-offs regarding multi-turn conversation depth, token economics, and LLM attention dilution in **SCRI Oncology Copilot**. It outlines how the current system balances grounding with token efficiency, and how enterprise production systems can scale this further.

---

## 1. Executive Summary

Clinical protocol screening is an exact, high-stakes information retrieval domain. Unlike consumer chat applications where conversational memory can stretch across dozens of turns, clinical trial screening requires **absolute verbatim precision** on every single turn.

In testing multi-turn sessions beyond 2–3 turns, two related challenges arise:
1. **Token Economics:** Resending verbatim conversation history containing multiple 400-word clinical answers causes quadratic token consumption, quickly burning API budgets.
2. **Attention Dilution ("Lost in the Middle"):** As conversation history accumulates, frontier LLMs (such as GPT-4o) naturally attenuate attention to the system prompt and newly retrieved passages, drifting from formal bracket-cited answers into colloquial summaries (*"typically, clinical trials require a few weeks..."*).

---

## 2. Current Implementation: The 3-Query Per Session Cap

### Why 3 Queries?
In real clinical practice at SCRI, Clinical Research Coordinators (CRCs) and Molecular Tumor Board (MTB) navigators screen patients in **short, focused bursts**:
* **Query 1:** Core Inclusion Criteria & Biomarker targets (*"What are the prior therapy requirements for NCT07659782?"*)
* **Query 2:** Washout Periods & Disqualifying Conditions (*"What about surgery or radiation washout for that same patient?"*)
* **Query 3:** Comparative or Lab Threshold Checks (*"Compare NCT07659782 with NCT06312137 for radiation washout"*)

Beyond 3 queries, the coordinator is almost always screening a new patient or shifting to a different tumor program, where prior conversational context becomes irrelevant noise that risks cross-contaminating eligibility criteria.

### Technical Guardrails in Place:
* **Session Hard Cap:** When a coordinator submits a 4th query in the same thread, the backend intercepts the request before calling the LLM and emits:
  > `⚠️ Screening Session Limit Reached (3/3 Queries)`  
  > *To guarantee strict protocol grounding, prevent token degradation, and maintain clinical safety, individual screening sessions are capped at 3 queries. Please click "New Chat" in the sidebar to start a fresh screening session for your next inquiry.*
* **Lean History Window (`MAX_HISTORY_TURNS = 2`):** Only the immediately preceding Q&A pair is passed into the LLM context, resolving pronouns (*"that same patient"*, *"the second trial"*) without dragging old essay text forward.
* **Direct Prompt-Level Citation Directive:** Appended directly to the user prompt so the LLM never omits bracket citations `[NCT ID, Section Header]`.
* **Corpus Manifest Pruning:** The full 25-trial manifest is withheld during specific eligibility questions, keeping 100% of the attention window on the retrieved protocol chunks.

---

## 3. Future Production Scaling Plan (Enterprise Expansion)

When moving to a fully enterprise-funded deployment with broader multi-turn requirements, the 3-query boundary can be expanded using the following architectural upgrades:

### 3.1 Frontier Long-Context Models
* **Approach:** Migrate to models with stronger needle-in-a-haystack attention retention across long contexts (e.g., Claude 3.5 Sonnet with 200k context or Gemini 1.5 Pro).
* **Benefit:** Significantly higher resistance to attention decay, maintaining verbatim citation adherence even after 10+ turns of conversation.

### 3.2 Dynamic Coreference Rewriting (Stand-Alone Query Synthesis)
* **Approach:** Use a lightweight, sub-second model (e.g., `gpt-4o-mini`) as a preprocessing step:
  * Input: Raw User Query + Conversation Transcript
  * Output: Standalone, de-referenced clinical query with all implicit entities resolved.
* **Benefit:** Completely eliminates the need to pass previous assistant responses into the primary LLM's context window. The primary model only sees the rewritten question and the fresh evidence, effectively making every turn a zero-baggage Turn 1.

### 3.3 Session-Level Evidence Cache (Redis / In-Memory Store)
* **Approach:** Store retrieved chunk IDs in a session cache keyed by `thread_id` (2-hour TTL).
* **Benefit:** When follow-up questions are asked, candidate passages from previous turns remain directly accessible in the cache without needing to re-fetch or rely on the LLM's context memory.

### 3.4 Conversation Summarizer / State Vector
* **Approach:** Instead of feeding raw chat text back into the LLM, maintain a structured JSON **Screening State Object**:
  ```json
  {
    "active_trial": "NCT07659782",
    "disease": "NSCLC KRAS G12D",
    "verified_criteria": ["Inclusion #6", "Exclusion #3", "Exclusion #4"]
  }
  ```
* **Benefit:** Condenses 2,000 tokens of chat history into ~50 tokens of state, permanently eliminating token bloat and context drift.
