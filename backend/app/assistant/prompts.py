"""Clinical prompt engineering and oncology system instructions for SCRI Oncology Copilot.

Enforces:
1. Zero Hallucination: Never guess, extrapolate, or generalize from other medical literature.
2. Mandatory Bracketed Citations: Every factual assertion must cite `[NCT ID, Section Header]`.
3. Negative Refusal: If the retrieved protocol context does not specify a criterion or threshold,
   the model must explicitly state: "The protocol does not state [X]."
4. Off-Corpus Refusal (audit finding C3): If NO passages were retrieved, or none address the
   disease / population / intervention in the question, the model must refuse from general
   medical knowledge rather than answer from its training data.
"""

from app.assistant.schemas import ProtocolPassage

SYSTEM_PROMPT = (
    "You are an expert oncology clinical trial assistant for Sarah Cannon Research Institute (SCRI). "
    "Your mission is to provide accurate, grounded answers to clinical research coordinators (CRCs), "
    "Molecular Tumor Board (MTB) navigators, and investigators screening cancer patients against trial protocols.\n\n"
    "CRITICAL CLINICAL RULES:\n"
    "0. ANSWER ONLY FROM THE PROVIDED PROTOCOL CONTEXT. You are FORBIDDEN from using your training "
    "knowledge, general medical literature, or 'standard of care' to answer. If the Protocol Context "
    "section states it is EMPTY, or none of the retrieved passages address the disease, population, "
    "intervention, or specific trial asked about in the question, you MUST refuse entirely and state "
    "exactly: 'This system does not contain protocol information for [topic]. The retrieved passages "
    "do not address this question.' Never describe what such protocols 'typically' or 'commonly' "
    "require — that is answering from memory, which is prohibited.\n"
    "1. PROTOCOL ACCESS & MULTI-TURN INDEPENDENCE: Relevant protocol excerpts from our active clinical trial "
    "database are supplied below in the 'Protocol Context' section for each turn. You ARE connected to the "
    "trial database and DO have access to these documents. NEVER state that you 'lack access to protocol "
    "documents or databases' or that you 'cannot access specific studies or trial details' when passages are "
    "provided in Protocol Context. Treat each question independently using the Protocol Context retrieved for "
    "that specific query: even if earlier turns in the conversation resulted in refusals, when the Protocol "
    "Context for the current question contains relevant passages, you MUST use them to answer and cite them.\n"
    "2. ABSOLUTE GROUNDING: Every single factual claim or clinical parameter must cite its supporting protocol passage "
    "using exact bracket notation: [NCT ID, Section Header] (e.g. [NCT07659782, Eligibility: Exclusion Criterion #4]).\n"
    "3. NO PLACEHOLDERS: NEVER use hypothetical placeholders like 'Trial X', 'Trial Y', or 'Trial A'. "
    "You must only reference real NCT identifiers present in the Protocol Context.\n"
    "4. ZERO HALLUCINATION / NEGATIVE REFUSAL: Never fabricate eligibility criteria, lab thresholds, prior therapy washout "
    "durations, or organ function limits. If the retrieved protocol context does not explicitly mention a criterion, "
    "you MUST state: 'The protocol does not state [X].' Never guess, extrapolate, or assume standard of care.\n"
    "5. EXCLUSIONS VS INCLUSIONS: Pay careful attention to whether a rule is an Inclusion or Exclusion criterion. "
    "An exclusion criterion means a patient with that condition is DISQUALIFIED from enrolling.\n"
    "6. CLINICAL CLARITY: Present answers in clear, professional medical language with bullet points and bold key terms "
    "so coordinators can review evidence in seconds."
)

# Directive injected into the system context when retrieval returns zero passages.
# This is an INSTRUCTION, not a status line: the model must be told what to do, not
# merely informed that nothing was found (audit finding C3 — a bare status line read
# like a retrieval hiccup and the model answered from general knowledge instead).
EMPTY_CONTEXT_DIRECTIVE = (
    "Protocol Context: EMPTY — no protocol passages in this system matched this query. "
    "You MUST NOT answer from general medical knowledge or training data. Respond that this "
    "system does not contain protocol information for the topic asked about."
)


def format_protocol_context(passages: list[ProtocolPassage]) -> str:
    """Format retrieved protocol passage chunks into numbered context blocks for prompt assembly."""
    if not passages:
        return EMPTY_CONTEXT_DIRECTIVE

    formatted_passages: list[str] = []
    for idx, p in enumerate(passages, start=1):
        formatted_passages.append(
            f"[Passage {idx} | {p.nct_id}, {p.section_header}]\n{p.chunk_text}"
        )
    return "Protocol Context:\n" + "\n\n".join(formatted_passages)


def format_corpus_manifest(category_counts: dict[str, int]) -> str:
    """Render a compact corpus manifest so 'which protocols are in this system' is answerable.

    Without this, the model has no way to truthfully answer coverage questions
    ("does this system have pediatric GBM protocols?") and is tempted to guess.
    """
    if not category_counts:
        return "Corpus Manifest: no clinical trials are currently loaded in this system."

    total = sum(category_counts.values())
    lines = [f"Corpus Manifest: this system contains {total} clinical trial protocol(s):"]
    for category in sorted(category_counts):
        lines.append(f"  - {category.replace('_', ' ')}: {category_counts[category]} trial(s)")
    lines.append(
        "Topics outside these disease areas are NOT in this system and must be refused."
    )
    return "\n".join(lines)


def build_no_evidence_refusal(query: str, category_counts: dict[str, int]) -> str:
    """Deterministic refusal emitted when retrieval returns zero relevant passages (C3).

    Deliberately NOT model-generated: with no evidence in hand, an LLM producing clinical
    text is itself a hallucination risk. This canned response is auditable, costs no
    tokens, and cannot drift.
    """
    topic = query.strip()
    if len(topic) > 120:
        topic = topic[:117] + "..."

    if category_counts:
        total = sum(category_counts.values())
        areas = ", ".join(c.replace("_", " ") for c in sorted(category_counts))
        scope = (
            f"This system currently contains {total} active trial protocols covering: {areas}. "
        )
    else:
        scope = "This system currently has no trial protocols loaded. "

    return (
        "I cannot answer this from the protocols in this system.\n\n"
        f"**Question:** {topic}\n\n"
        f"{scope}"
        "No protocol passages matched this question, so per this system's grounding rules I will not "
        "answer from general medical knowledge. If you are screening for a disease area not listed "
        "above, it is not represented in the current trial corpus — please verify directly in OnCore "
        "or with the study team."
    )
