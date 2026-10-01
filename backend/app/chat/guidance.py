"""Conversational greeting, capability orientation, and trial catalog guidance router.

Enforces:
1. Fast Intent Classification: Deterministically recognizes greetings ("hello"),
   capability questions ("what can you tell me?"), and catalog inquiries ("what trials are loaded?")
   in 0ms without hitting vector search, full-text search, or OpenAI LLM APIs.
2. Clinical Safety Preservation: Any query containing an explicit NCT ID or clinical
   oncology parameters (e.g. brain metastases, washout, ANC, EGFR, ECOG) is strictly routed to the
   hybrid retrieval pipeline rather than caught here.
3. Quota Exemption: Guidance and greeting turns do NOT consume the coordinator's
   3-query screening session quota (MAX_QUERIES_PER_SESSION).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)

# Distinct clinical oncology terms that indicate an actual protocol screening inquiry
CLINICAL_INDICATORS = frozenset(
    {
        "washout",
        "metastases",
        "metastasis",
        "metastatic",
        "lesion",
        "lesions",
        "biomarker",
        "mutation",
        "alteration",
        "egfr",
        "kras",
        "braf",
        "her2",
        "pd-l1",
        "pdl1",
        "anc",
        "platelet",
        "platelets",
        "neutrophil",
        "neutrophils",
        "bilirubin",
        "creatinine",
        "ast",
        "alt",
        "dlt",
        "ecog",
        "kps",
        "car-t",
        "cart",
        "chemo",
        "chemotherapy",
        "radiation",
        "radiotherapy",
        "immunotherapy",
        "steroid",
        "steroids",
        "cns",
        "mri",
        "ct",
        "recist",
        "refractory",
        "line of therapy",
        "lines of therapy",
        "prior therapy",
        "prior therapies",
        "dose escalation",
        "expansion",
    }
)

GREETING_PATTERNS = [
    re.compile(r"^hi(\s+(there|copilot|scri|all|team))?$", re.IGNORECASE),
    re.compile(r"^hello(\s+(there|copilot|scri|all|team))?$", re.IGNORECASE),
    re.compile(r"^hey(\s+(there|copilot|scri|all|team))?$", re.IGNORECASE),
    re.compile(r"^good\s+(morning|afternoon|evening|day)$", re.IGNORECASE),
    re.compile(r"^howdy$", re.IGNORECASE),
    re.compile(r"^greetings$", re.IGNORECASE),
    re.compile(r"^salutations$", re.IGNORECASE),
]

CAPABILITY_PATTERNS = [
    re.compile(
        r"^(what|how)\s+(can|do)\s+(you|i)\s+(do|tell(\s+me)?|ask(\s+you)?|know)(\s+about)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^what\s+(are\s+your\s+capabilities|can\s+you\s+help(\s+me)?\s+with)$", re.IGNORECASE
    ),
    re.compile(r"^how\s+can\s+you\s+help(\s+me)?$", re.IGNORECASE),
    re.compile(r"^how\s+does\s+this\s+(work|app|copilot|system)(\s+work)?$", re.IGNORECASE),
    re.compile(r"^how\s+do\s+i\s+use\s+(this|scri|copilot|the\s+system)$", re.IGNORECASE),
    re.compile(r"^(who|what)\s+are\s+you$", re.IGNORECASE),
    re.compile(r"^what\s+is\s+(this|scri|scri\s+copilot|this\s+system|this\s+app)$", re.IGNORECASE),
    re.compile(r"^help(\s+me)?$", re.IGNORECASE),
    re.compile(r"^guide(\s+me)?$", re.IGNORECASE),
    re.compile(r"^(usage|user\s+guide|instructions)$", re.IGNORECASE),
]

CATALOG_PATTERNS = [
    re.compile(
        r"^(what|which)\s+(trials|protocols|studies|diseases|cancer\s+types|categories)\s+"
        r"(are\s+(in|loaded|available|active)|do\s+you\s+(have|cover|contain))(\s+in\s+this\s+system)?$",
        re.IGNORECASE,
    ),
    re.compile(r"^(what|which)\s+(trials|protocols|studies)\s+do\s+you\s+have$", re.IGNORECASE),
    re.compile(
        r"^list(\s+all)?\s+(trials|protocols|studies|diseases|cancer\s+types)$", re.IGNORECASE
    ),
    re.compile(
        r"^show(\s+all)?\s+(trials|protocols|studies|diseases|active\s+trials)$", re.IGNORECASE
    ),
    re.compile(
        r"^how\s+many\s+(trials|protocols|studies)\s+(are\s+there|are\s+loaded|do\s+you\s+have)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(what\s+is\s+the\s+)?(catalog|corpus)\s*(manifest|coverage|scope)?$", re.IGNORECASE
    ),
]


def normalize_query_text(query: str) -> str:
    """Strip leading/trailing whitespace, punctuation, and multi-spaces."""
    cleaned = query.strip()
    cleaned = re.sub(r"[?!.,;:]+$", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _has_clinical_indicators(cleaned_lower: str) -> bool:
    """Check if query contains specific clinical oncology keywords."""
    words = re.findall(r"[a-z0-9-]+", cleaned_lower)
    return any(w in CLINICAL_INDICATORS for w in words)


def classify_guidance_intent(query: str) -> str | None:
    """Classify user query into guidance/greeting intent if non-clinical.

    Returns:
        - "greeting" for greetings ("hello", "hi")
        - "capabilities" for capability questions ("what can you do", "what can you tell me")
        - "catalog" for trial coverage questions ("what trials are loaded", "list trials")
        - None for all actual clinical protocol questions or questions with medical entities.
    """
    cleaned = normalize_query_text(query)
    if not cleaned:
        return None

    # Safety Guard 1: Any explicit NCT ID belongs to protocol retrieval
    if NCT_RE.search(cleaned):
        return None

    # Safety Guard 2: Any query containing specific clinical indicators belongs to protocol retrieval
    if _has_clinical_indicators(cleaned.lower()):
        return None

    # Check Greeting patterns
    for pat in GREETING_PATTERNS:
        if pat.match(cleaned):
            return "greeting"

    # Check Capability patterns
    for pat in CAPABILITY_PATTERNS:
        if pat.match(cleaned):
            return "capabilities"

    # Check Catalog patterns
    for pat in CATALOG_PATTERNS:
        if pat.match(cleaned):
            return "catalog"

    return None


def is_guidance_intent(query: str) -> bool:
    """Check if query is a greeting, capability query, or catalog overview inquiry."""
    return classify_guidance_intent(query) is not None


def format_category_name(category: str) -> str:
    """Format category slug into clean clinical title."""
    return category.replace("_", " ").title()


def build_guidance_response(
    intent: str,
    corpus_manifest: dict[str, int],
) -> str:
    """Build grounded, comprehensive orientation guidance for coordinators.

    Includes:
    - Welcome and role identity
    - Primary clinical capabilities (washout, labs, biomarkers, comparison)
    - Dynamically populated active trial corpus manifest
    - 4 concrete exemplary queries matching UI cards
    - Grounding notice and session quota exemption indicator
    """
    total_trials = sum(corpus_manifest.values()) if corpus_manifest else 0
    if corpus_manifest:
        disease_items = "\n".join(
            f"  - **{format_category_name(cat)}**: {count} active protocol{'s' if count != 1 else ''}"
            for cat, count in sorted(corpus_manifest.items())
        )
    else:
        disease_items = "  - *No clinical trial protocols currently loaded in database.*"

    greeting_headline = (
        "### 👋 Welcome to SCRI Oncology Protocol Copilot"
        if intent == "greeting"
        else "### ℹ️ SCRI Oncology Protocol Copilot — Capabilities & Guide"
    )

    return (
        f"{greeting_headline}\n\n"
        "I am an intelligent clinical trial protocol assistant designed for **Clinical Research Coordinators (CRCs)**, "
        "**Molecular Tumor Board (MTB) navigators**, and **Principal Investigators** across the Sarah Cannon Research Institute (SCRI) network.\n\n"
        "I provide instant, grounded answers to plain-English questions across active trial protocols to accelerate patient intake.\n\n"
        "---\n\n"
        "#### 🎯 What You Can Ask Me:\n"
        "- **Eligibility Criteria:** Check prior therapy washouts, ECOG performance status, and brain metastases stability.\n"
        "- **Biomarker & Genomic Targets:** Confirm required alterations (e.g. *EGFR Exon 20*, *KRAS G12D*, *HER2-low*, *PD-L1*, *BRAF V600E*).\n"
        "- **Laboratory & Organ Function Limits:** Check baseline thresholds for ANC, platelets, total bilirubin, AST/ALT, and creatinine clearance.\n"
        "- **CNS & Brain Metastases Rules:** Review stability windows, stereotactic radiosurgery intervals, and asymptomatic requirements.\n"
        "- **Cross-Trial Comparison:** Compare eligibility criteria across Phase 1, 2, or 3 protocols side-by-side with isolated citations.\n\n"
        "---\n\n"
        f"#### 📚 Active Trial Corpus Coverage ({total_trials} Protocols Loaded):\n"
        f"{disease_items}\n\n"
        "*(You can also browse the full protocol catalog and inspect source documents under the **Trial Catalog** tab at the top right).*\n\n"
        "---\n\n"
        "#### 💡 Exemplary Queries to Try:\n"
        "1. **Prior Immunotherapy Washouts (Lung / Lymphoma):**\n"
        '   > *"Across our active lymphoma and lung cancer trials, which protocols require a 28-day washout for prior checkpoint inhibitor therapy versus a 14-day or 5 half-life washout?"*\n\n'
        "2. **Brain Metastases Stability (Colorectal):**\n"
        '   > *"Which active Phase 2/3 colorectal cancer protocols permit patients with pre-treated, asymptomatic brain metastases, and what is the required MRI stability interval prior to Cycle 1 Day 1?"*\n\n'
        "3. **Baseline Hematologic Limits (CAR-T / Phase 1):**\n"
        '   > *"Compare the baseline hematologic thresholds across our active Phase 1 CAR-T studies. Which protocol allows an absolute neutrophil count (ANC) below 1,000/µL or platelets below 75,000/µL?"*\n\n'
        "4. **Prior Lines of Therapy (Breast / Metastatic):**\n"
        '   > *"Which breast cancer trials require patients to have received at least 2 prior lines of systemic therapy in the metastatic setting, and which accept first-line refractory patients?"*\n\n'
        "---\n\n"
        "> ℹ️ **Clinical Safety & Grounding Notice:**\n"
        "> Every factual assertion in screening answers is backed by exact protocol citations `[NCT ID, Section Header]` linked to source documents.\n"
        "> *Note: General greetings and capability questions do not count against your 3-query clinical screening quota.*"
    )
