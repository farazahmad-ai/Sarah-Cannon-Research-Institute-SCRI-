"""Clinical prompt engineering and oncology system instructions for SCRI Oncology Copilot.

Enforces:
1. Zero Hallucination: Never guess, extrapolate, or generalize from other medical literature.
2. Mandatory Bracketed Citations: Every factual assertion must cite `[NCT ID, Section Header]`.
3. Negative Refusal: If the retrieved protocol context does not specify a criterion or threshold,
   the model must explicitly state: "The protocol does not state [X]."
"""

from app.assistant.schemas import ProtocolPassage
from app.database.models import ChatMessage

SYSTEM_PROMPT = (
    "You are an expert oncology clinical trial assistant for Sarah Cannon Research Institute (SCRI). "
    "Your mission is to provide accurate, grounded answers to clinical research coordinators (CRCs), "
    "Molecular Tumor Board (MTB) navigators, and investigators screening cancer patients against trial protocols.\n\n"
    "CRITICAL CLINICAL RULES:\n"
    "1. ABSOLUTE GROUNDING: Every single factual claim or clinical parameter must cite its supporting protocol passage "
    "using exact bracket notation: [NCT ID, Section Header] (e.g. [NCT07659782, Eligibility: Exclusion Criterion #4]).\n"
    "2. ZERO HALLUCINATION / NEGATIVE REFUSAL: Never fabricate eligibility criteria, lab thresholds, prior therapy washout "
    "durations, or organ function limits. If the retrieved protocol context does not explicitly mention a criterion, "
    "you MUST state: 'The protocol does not state [X].' Never guess, extrapolate, or assume standard of care.\n"
    "3. EXCLUSIONS VS INCLUSIONS: Pay careful attention to whether a rule is an Inclusion or Exclusion criterion. "
    "An exclusion criterion means a patient with that condition is DISQUALIFIED from enrolling.\n"
    "4. CLINICAL CLARITY: Present answers in clear, professional medical language with bullet points and bold key terms "
    "so coordinators can review evidence in seconds."
)


def format_protocol_context(passages: list[ProtocolPassage]) -> str:
    """Format retrieved protocol passage chunks into numbered context blocks for prompt assembly."""
    if not passages:
        return "Protocol Context: No matching protocol passages retrieved for this query."

    formatted_passages: list[str] = []
    for idx, p in enumerate(passages, start=1):
        formatted_passages.append(
            f"[Passage {idx} | {p.nct_id}, {p.section_header}]\n{p.chunk_text}"
        )
    return "Protocol Context:\n" + "\n\n".join(formatted_passages)


def build_chat_messages(
    history: list[ChatMessage],
    passages: list[ProtocolPassage],
    user_query: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> list[dict[str, str]]:
    """Assemble standard OpenAI/OpenRouter chat messages array with system, history, and context."""
    system_entry = {
        "role": "system",
        "content": system_prompt,
    }

    prior_entries: list[dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in history
    ]

    context_block = format_protocol_context(passages)
    user_content = f"{context_block}\n\nQuestion: {user_query}"

    user_entry = {
        "role": "user",
        "content": user_content,
    }

    return [system_entry, *prior_entries, user_entry]
