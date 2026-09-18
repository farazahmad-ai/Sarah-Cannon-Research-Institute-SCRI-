# /// script
# requires-python = ">=3.12"
# ///
"""Sarah Cannon Research Institute (SCRI) — Clinical Trial Protocol Downloader.

Fetches curated landmark interventional oncology trial protocols from the
official ClinicalTrials.gov REST API v2, saves structured protocol payloads,
and compiles a manifest for ingestion into Supabase pgvector.

Run:
    uv run data/download.py
"""

from __future__ import annotations

import json
import re
import shutil
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib import error, parse, request

# Configuration: Edit these parameters as needed
USER_AGENT = "SCRI-Protocol-Copilot research@scri.com"
OUTPUT_DIR = Path(__file__).resolve().parent / "downloads"
CLEAR_OUTPUT_DIR = True
STUDIES_PER_CATEGORY = 5

# Core oncology categories aligned with Sarah Cannon Research Institute focus areas
ONCOLOGY_CATEGORIES = {
    "non_small_cell_lung_cancer": {
        "label": "Non-Small Cell Lung Cancer (NSCLC)",
        "query_term": "Non-Small Cell Lung Cancer",
    },
    "lymphoma_car_t": {
        "label": "Large B-Cell Lymphoma & CAR-T / Bispecifics",
        "query_term": "Diffuse Large B-Cell Lymphoma",
    },
    "colorectal_cancer": {
        "label": "Metastatic Colorectal Cancer (mCRC)",
        "query_term": "Colorectal Neoplasms",
    },
    "breast_cancer": {
        "label": "Triple-Negative & HER2-Low Breast Cancer",
        "query_term": "Triple Negative Breast Neoplasms",
    },
    "melanoma": {
        "label": "Advanced & Metastatic Melanoma",
        "query_term": "Melanoma",
    },
}

API_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def get_json(url: str) -> dict:
    """Fetch JSON payload from a remote URL."""
    headers = {
        "Accept": "*/*",
        "User-Agent": USER_AGENT,
    }
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except ssl.SSLError:
        ctx = ssl._create_unverified_context()
        with request.urlopen(req, context=ctx, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))


def download_protocols() -> dict:
    """Download oncology trial protocols from ClinicalTrials.gov and build manifest."""
    if CLEAR_OUTPUT_DIR and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": "ClinicalTrials.gov REST API v2",
        "institution": "Sarah Cannon Research Institute (SCRI)",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "downloaded_count": 0,
        "categories": list(ONCOLOGY_CATEGORIES.keys()),
        "studies": [],
    }

    seen_nct_ids: set[str] = set()

    for cat_key, cat_meta in ONCOLOGY_CATEGORIES.items():
        print(f"Fetching {cat_meta['label']} protocols...")
        cat_dir = OUTPUT_DIR / cat_key
        cat_dir.mkdir(parents=True, exist_ok=True)

        params = {
            "query.cond": cat_meta["query_term"],
            "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
            "sort": "LastUpdatePostDate:desc",
            "pageSize": str(STUDIES_PER_CATEGORY * 2),
        }
        query_url = f"{API_BASE_URL}?{parse.urlencode(params)}"

        try:
            payload = get_json(query_url)
        except Exception as exc:
            print(f"  Warning: failed to query {cat_key}: {exc}")
            continue

        raw_studies = payload.get("studies", [])
        saved_for_category = 0

        for item in raw_studies:
            if saved_for_category >= STUDIES_PER_CATEGORY:
                break

            protocol = item.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            nct_id = id_module.get("nctId")
            if not nct_id or nct_id in seen_nct_ids:
                continue

            seen_nct_ids.add(nct_id)

            brief_title = id_module.get("briefTitle", "Untitled Study")
            official_title = id_module.get("officialTitle", brief_title)
            org_name = id_module.get("organization", {}).get("fullName", "Unknown Organization")
            status_module = protocol.get("statusModule", {})
            status = status_module.get("overallStatus", "UNKNOWN")
            start_date = status_module.get("startDateStruct", {}).get("date", "N/A")
            last_update_date = status_module.get("lastUpdatePostDateStruct", {}).get("date", "N/A")
            primary_completion_date = status_module.get("primaryCompletionDateStruct", {}).get("date", "N/A")
            phases = protocol.get("designModule", {}).get("phases", [])
            conditions = protocol.get("conditionsModule", {}).get("conditions", [])
            eligibility_text = protocol.get("eligibilityModule", {}).get("eligibilityCriteria", "")

            # Extract arms and interventions
            arm_groups = protocol.get("armsInterventionsModule", {}).get("armGroups", [])
            formatted_arms = []
            for idx, arm in enumerate(arm_groups, 1):
                label = arm.get("label", "Unnamed Arm")
                arm_type = arm.get("type", "")
                desc = arm.get("description", "")
                interventions = arm.get("interventionNames", [])
                arm_entry = f"Arm {idx}: {label}" + (f" ({arm_type})" if arm_type else "")
                if desc:
                    arm_entry += f"\n  Description: {desc}"
                if interventions:
                    arm_entry += f"\n  Interventions: {', '.join(interventions)}"
                formatted_arms.append(arm_entry)
            arms_text = "\n\n".join(formatted_arms) if formatted_arms else "N/A"

            # Extract primary outcomes
            primary_outcomes = protocol.get("outcomesModule", {}).get("primaryOutcomes", [])
            formatted_outcomes = []
            for idx, po in enumerate(primary_outcomes, 1):
                measure = po.get("measure", "")
                timeframe = po.get("timeFrame", "")
                desc = po.get("description", "")
                entry = f"{idx}. {measure}"
                if timeframe:
                    entry += f" [Time Frame: {timeframe}]"
                if desc:
                    entry += f"\n   Description: {desc}"
                formatted_outcomes.append(entry)
            outcomes_text = "\n\n".join(formatted_outcomes) if formatted_outcomes else "N/A"

            # Detailed description & summary
            desc_module = protocol.get("descriptionModule", {})
            brief_summary = desc_module.get("briefSummary", "N/A")
            detailed_desc = desc_module.get("detailedDescription")

            # Save full study JSON
            json_filename = f"{nct_id.lower()}.json"
            json_file_path = cat_dir / json_filename
            json_file_path.write_text(json.dumps(item, indent=2), encoding="utf-8")

            # Save human-readable formatted protocol text
            txt_filename = f"{nct_id.lower()}_protocol.txt"
            txt_file_path = cat_dir / txt_filename
            txt_content = (
                f"TRIAL ID: {nct_id}\n"
                f"BRIEF TITLE: {brief_title}\n"
                f"OFFICIAL TITLE: {official_title}\n"
                f"LEAD ORGANIZATION: {org_name}\n"
                f"STATUS: {status}\n"
                f"LAST UPDATE POSTED: {last_update_date}\n"
                f"START DATE: {start_date}\n"
                f"PRIMARY COMPLETION DATE: {primary_completion_date}\n"
                f"PHASES: {', '.join(phases) if phases else 'N/A'}\n"
                f"CONDITIONS: {', '.join(conditions)}\n"
                f"SOURCE URL: https://clinicaltrials.gov/study/{nct_id}\n\n"
                f"{'='*60}\n"
                f"BRIEF SUMMARY\n"
                f"{'='*60}\n"
                f"{brief_summary}\n\n"
            )
            if detailed_desc:
                txt_content += (
                    f"{'='*60}\n"
                    f"DETAILED DESCRIPTION\n"
                    f"{'='*60}\n"
                    f"{detailed_desc}\n\n"
                )
            txt_content += (
                f"{'='*60}\n"
                f"STUDY ARMS & INTERVENTIONS\n"
                f"{'='*60}\n"
                f"{arms_text}\n\n"
                f"{'='*60}\n"
                f"PRIMARY OUTCOME MEASURES\n"
                f"{'='*60}\n"
                f"{outcomes_text}\n\n"
                f"{'='*60}\n"
                f"ELIGIBILITY CRITERIA (INCLUSION & EXCLUSION)\n"
                f"{'='*60}\n"
                f"{eligibility_text}\n"
            )
            txt_file_path.write_text(txt_content, encoding="utf-8")

            manifest["studies"].append(
                {
                    "nct_id": nct_id,
                    "category": cat_key,
                    "brief_title": brief_title,
                    "official_title": official_title,
                    "organization": org_name,
                    "status": status,
                    "last_update_posted_date": last_update_date,
                    "start_date": start_date,
                    "primary_completion_date": primary_completion_date,
                    "phases": phases,
                    "conditions": conditions,
                    "source_url": f"https://clinicaltrials.gov/study/{nct_id}",
                    "local_json_path": str(json_file_path.relative_to(OUTPUT_DIR)),
                    "local_txt_path": str(txt_file_path.relative_to(OUTPUT_DIR)),
                }
            )

            manifest["downloaded_count"] += 1
            saved_for_category += 1
            time.sleep(0.15)

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = download_protocols()
    print(f"Downloaded {result['downloaded_count']} trial protocol(s) to {OUTPUT_DIR}")
    print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")
