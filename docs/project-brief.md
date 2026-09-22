# Client Brief & Case Study — Sarah Cannon Research Institute (SCRI)
*(Real-World Oncology Clinical Trial Network Case Study)*

## The Client

**Sarah Cannon Research Institute (SCRI)** is one of the world's leading oncology research organizations and clinical trial networks. Operating as the research arm of HCA Healthcare, SCRI conducts clinical trials across more than 250 oncology clinic sites across the United States and the United Kingdom.

SCRI enrolls over 4,500 cancer patients annually into clinical trials and has conducted more than 750 first-in-human clinical trials. They have played a pivotal role in the clinical development and FDA approval of the majority of novel cancer therapies approved over the past two decades.

## Operational Model & How Value is Created

- **Decentralized Community Network:** Rather than forcing terminal or refractory cancer patients to travel across the country to academic ivory towers, SCRI brings cutting-edge Phase 1–3 clinical trials directly into local community cancer clinics.
- **Biopharma Partnerships:** Pharmaceutical and biotechnology sponsors (such as AstraZeneca, Merck, Genentech, and emerging biotechs) partner with SCRI to execute fast, high-compliance clinical trials.
- **Precision Matching:** Patients undergo Next-Generation Sequencing (NGS) genomic profiling (Foundation Medicine, Guardant360, Tempus). SCRI's **Molecular Tumor Boards (MTB)** and dedicated **Clinical Research Coordinators (CRCs)** match patients harboring specific biomarkers (e.g., *KRAS G12C*, *HER2-low*, *EGFR Exon 20*, *TROP2*, *claudin 18.2*) to active investigational protocols.
- **The Stakes:** Trial matching is life-or-death. If a coordinator misses an open study or misinterprets an eligibility clause, a patient with rapid disease progression misses their final therapeutic window. Conversely, enrolling a patient who fails an exclusion criterion (e.g., active autoimmune disease or inadequate washout) leads to dangerous adverse toxicities and an official FDA/Sponsor protocol violation.

## The Problem: The "Protocol Burden" Bottleneck

A clinical research coordinator (CRC) at an active SCRI community site is responsible for screening dozens of patients weekly against an active portfolio of **40 to 80 open trial protocols**.

Each protocol is an exhaustive **100 to 250-page technical document** with complex amendments, appendices, and multi-layered inclusion/exclusion criteria.

### The Daily Friction:
1. **The 20-Hour Intake Grind:** CRCs and research nurses report spending **15–20 hours every week** manually opening PDFs, hitting `Ctrl+F`, and scanning through dense eligibility sections to answer hyper-specific questions:
   * *“Does Protocol X permit patients who received stereotactic radiosurgery for brain metastases 3 weeks ago?”*
   * *“What is the minimum required absolute neutrophil count (ANC) and platelet count for Arm B?”*
   * *“Is a 14-day washout sufficient for prior anti-PD-1 therapy, or does this study demand 28 days?”*
2. **Amendment Fatigue:** Protocols are amended multiple times per year. Coordinators must constantly verify whether an inclusion criteria update or dose-reduction guideline applies to Version 3.1 vs Version 4.0.
3. **Duplicated Labor Across Network Sites:** Research coordinators in Nashville, Denver, Kansas City, and London independently spend hours reading and deciphering the exact same 180-page Phase 3 bispecific antibody protocol.

Adding more coordinators does not solve this bottleneck; the cognitive overhead scales linearly with protocol volume and complexity.

## The Solution: SCRI Oncology Copilot

An internal, web-based AI intelligence assistant deployed for SCRI coordinators, investigators, and Molecular Tumor Board navigators:

- **Natural Language Protocol Interrogation:** Coordinators ask questions in plain English across the active trial corpus.
- **Verbatim Grounded Citations:** Every answer references the specific **NCT ID**, section header, and paragraph (e.g., *NCT05794958 — Eligibility Module: Exclusion Criterion #4*).
- **One-Click Evidence Verification:** Clicking a citation displays the exact verbatim text from the trial protocol, allowing the clinician or CRC to confirm the rule in 5 seconds without leaving their workflow.
- **Strict Anti-Hallucination Guardrail:** The system refuses to extrapolate or assume criteria. If a protocol does not explicitly mention a requirement (such as a specific rare lab threshold or prior malignancy rule), the model explicitly states that the document is silent on that topic.
- **Zero HIPAA Exposure:** By restricting the tool’s scope strictly to **trial protocols** (which are public or sponsor-provided study parameters) rather than individual patient health records (PHI/EHR), the deployment bypasses enterprise HIPAA and EHR write-access friction.

## Real Trial Corpus (Pilot Phase)

The pilot corpus consists of **25 landmark interventional oncology trials** (5 per disease category) fetched directly from the **ClinicalTrials.gov REST API v2**, representing core SCRI focus areas:

1. **Thoracic Oncology (NSCLC):** Targeting *EGFR*, *ALK*, *KRAS G12C*, *ROS1*, and *MET* exon 14 skipping.
2. **Hematologic Malignancies (DLBCL & CAR-T / Bispecifics):** Novel CAR-T cell re-infusion protocols, CD19/CD20 bispecific antibodies, and cellular therapies.
3. **Gastrointestinal & Colorectal Cancers (mCRC):** Microsatellite Instability (MSI-H / dMMR), *BRAF V600E*, and HER2-amplified metastatic colorectal trials.
4. **Breast Cancers (TNBC & HER2-Low):** Antibody-Drug Conjugates (ADCs) like Trastuzumab deruxtecan and Sacituzumab govitecan in HER2-low and triple-negative breast cancer.
5. **Advanced & Metastatic Melanoma:** Immune checkpoint inhibitors, BRAF/MEK targeted therapies, and novel combination immunotherapies.

## 10 Realistic Coordinator Queries

1. **Prior Immunotherapy Washouts:** *"Across our active lymphoma and lung cancer trials, which protocols require a 28-day washout for prior checkpoint inhibitor therapy versus a 14-day or 5 half-life washout?"*
2. **CNS / Brain Metastases Eligibility:** *"Which active Phase 2/3 colorectal cancer protocols permit patients with pre-treated, asymptomatic brain metastases, and what is the required MRI stability interval prior to Cycle 1 Day 1?"*
3. **Hematologic Lab Limits:** *"Compare the baseline hematologic thresholds across our active Phase 1 CAR-T studies. Which protocol allows an absolute neutrophil count (ANC) below 1,000/µL or platelets below 75,000/µL?"*
4. **Bridging Therapy Guidelines:** *"In protocol NCT05794958 (Axicabtagene Ciloleucel reinfusion), what specific bridging therapies are permitted while waiting for CAR-T manufacturing, and are corticosteroids restricted?"*
5. **Dose-Limiting Toxicity (DLT) Definitions:** *"In the safety run-in phase for study [NCT ID], what specific Grade 3 or 4 adverse events trigger a Dose-Limiting Toxicity (DLT) determination during the first 28 days?"*
6. **Prior Systemic Therapy Limits:** *"Which breast cancer trials require patients to have received at least 2 prior lines of systemic therapy in the metastatic setting, and which trials accept first-line refractory patients?"*
7. **Organ Impairment Tolerances:** *"What are the exact renal function thresholds (Cockcroft-Gault CrCl or eGFR) across the active platinum-combination trials?"*
8. **Concomitant Medication Exclusions:** *"Which of our targeted kinase inhibitor trials explicitly prohibit concurrent administration of strong CYP3A4 inducers or proton pump inhibitors (PPIs)?"*
9. **Prior Malignancy Intervals:** *"What is the required disease-free interval for patients with a secondary prior cancer diagnosis, and which in situ or localized skin cancers are exempted from exclusion?"*
10. **Protocol Silence / Anti-Hallucination:** *"Does trial NCT02277548 permit patients with moderate hepatic impairment (Child-Pugh B)? Cite the exact text or confirm if the eligibility section does not specify hepatic parameters."*

## Architecture & Integration Boundaries

- **Web Frontend:** Vite + React + TypeScript + Tailwind CSS (hosted on Railway).
- **Backend Service:** FastAPI + PydanticAI + OpenAI embeddings and generation.
- **Database & Retrieval:** Supabase Postgres (`pgvector` for semantic search + Postgres full-text search with Reciprocal Rank Fusion).
- **Authentication:** Supabase Auth (institutional email restricted to `@scri.com` / `@hcahealthcare.com`).
- **Coexistence with Existing IT:**
  * **Epic Beacon (EHR):** Clinicians review patient charts in Epic; when an eligible trial is suspected, coordinators turn to SCRI Oncology Copilot to cross-reference protocol criteria in real time.
  * **OnCore (CTMS):** Protocol statuses (Open, Suspended, Closed to Accrual) stay synced in OnCore; SCRI Oncology Copilot provides the deep content intelligence.

## Pilot Success Criteria (Definition of Done)

A pilot working group of **6 Clinical Research Coordinators** across two regional SCRI research sites uses SCRI Oncology Copilot for 2 weeks during daily screening workflows. 

Success is achieved if:
1. **Quantified Time Savings:** Each coordinator saves a minimum of **3.5 hours per week** on protocol criteria searches.
2. **Zero Inaccurate Criteria Reported:** 100% of generated answers are verified against source protocol citations with zero fabricated eligibility criteria.
3. **Investigator Trust:** The pilot group rates the system at ≥ 8.5/10 on the clinical trust and citation inspectability index.
