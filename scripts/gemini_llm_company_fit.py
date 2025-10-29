import os
import pandas as pd
import json
import re
from dotenv import load_dotenv
from google import genai
from datetime import datetime

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

INPUTFILE = "../data/transportation_data_20251013_135544.parquet"
SAMPLESIZE = 100
SEED = 20
MODEL = "gemini-2.5-pro"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M")
OUTPUTDIR = "../llm/output/"
OUTPUT_SAMPLE = os.path.join(OUTPUTDIR, f"company-fit-sample-records_{TIMESTAMP}.csv")
OUTPUT_RESULTS = os.path.join(OUTPUTDIR, f"company-fit-results_{MODEL}_{TIMESTAMP}.csv")

def parse_file_date(filename):
    match = re.search(r'(\d{8})_\d{6}\.parquet$', filename)
    if match:
        extracted_date = match.group(1)
        parsed_date = datetime.strptime(extracted_date, "%Y%m%d")
        return parsed_date.strftime("%B %d, %Y")
    return "Unknown"

# --- MAIN SCRIPT ---
def main():
    os.makedirs(OUTPUTDIR, exist_ok=True)

    # Load data
    df = pd.read_parquet(INPUTFILE)
    print(f"Loaded {len(df)} records from {INPUTFILE}")

    dot_col = "dot_number"
    
    # Sample records
    sampledf = df.sample(n=SAMPLESIZE, random_state=SEED)
    print(f"Sampled {len(sampledf)} records for LLM evaluation")
    
    sampledf.to_csv(OUTPUT_SAMPLE, index=False)
    print(f"Sampled records saved to {OUTPUT_SAMPLE}")
    
    # Date context
    today_str = datetime.now().strftime("%B %d, %Y")
    file_date_str = parse_file_date(INPUTFILE)
    date_context = (
        f"The dataset was created on {file_date_str}. "
        f"Today's date is {today_str}. "
        "Use this date context for recency checks."
    )

    # System prompt
    systemprompt = f"""
ou are classifying U.S. trucking companies for DrivePoints Insurance.
Decide whether each company is GOOD or BAD. Make a balanced, evidence-based decision.

{date_context}

Do NOT default to BAD when uncertain. Only classify as BAD if a clear exclusion applies.
If multiple positive indicators are present and no exclusions, classify as GOOD.

---

### HARD EXCLUSIONS (always BAD)
If any of the following are true, classify as BAD and list all reasons in key_concerns:
- carrier_operation = "A" (Interstate)
- hm_flag = TRUE
- phy_state ∈ {{NJ, NY, PR, AK, HI}}
- us_mail = TRUE
- pc_flag = TRUE
- Defunct, inactive, or missing operational data
- Not a trucking company (e.g., construction-only, farming-only, towing-only)
- Government, school, or public agency

---

### POSITIVE INDICATORS (GOOD)
If most of the following hold and no exclusions apply, classify as GOOD:
- authorized_for_hire = TRUE (or Private with delivery/logistics operations implied by data)
- Operates in non-excluded states (priority but not required: CA, TX, AZ, UT, NV)
- Fleet size 1–50 (ideal 3–20)
- Recent activity (MCS-150 date 2023–2025 and/or active mileage)
- Metrics plausibility (e.g., miles per truck/year ~45K–120K; driver/truck ratio 0.8–1.5)
- Legitimate trucking identity (plausible name; consistent data across fields)

When evidence is mixed and no hard exclusions apply, decide proportionally—do not default to BAD.

---

### DECISION PLAN (internal)
1) Check hard exclusions. If any → BAD.
2) Otherwise evaluate legitimacy, freshness, fleet size, and metric plausibility.
3) Multiple positive indicators → GOOD.
4) If mixed, weigh recency + fleet range + plausibility; do NOT default to BAD.
5) Output a concise one-sentence rationale.

Do not reveal this plan; only output the required JSON.

---

### OUTPUT FORMAT
Return ONLY valid JSON (no extra text, no markdown):

{{
  "dot_number": "<DOT>",
  "company_name": "<legal_name or dba_name>",
  "classification": "GOOD" or "BAD",
  "key_concerns": ["<concern1>", "<concern2>", "..."],
  "reasoning_summary": "<short, clear rationale>"
}}

---

### FEW-SHOT CALIBRATION (no cargo fields)

# Example GOOD
Input:
carrier_operation="B", hm_flag=FALSE, phy_state="TX", authorized_for_hire=TRUE, fleet_size=12, mcs150_date="2024-05-10", annual_mileage=900000, trucks=10, drivers=11
Expected JSON:
{{
  "dot_number": "1234567",
  "company_name": "Lone Star Local Freight LLC",
  "classification": "GOOD",
  "key_concerns": [],
  "reasoning_summary": "Active for-hire carrier in a non-excluded state with small fleet, recent filing, and plausible mileage/driver ratios; no exclusions."
}}

# Example BAD
Input:
carrier_operation="A", hm_flag=TRUE, phy_state="NJ", authorized_for_hire=TRUE, fleet_size=8, mcs150_date="2023-11-02"
Expected JSON:
{{
  "dot_number": "9876543",
  "company_name": "Garden State Transport",
  "classification": "BAD",
  "key_concerns": ["Interstate operation", "Hazardous materials", "Excluded state NJ"],
  "reasoning_summary": "Fails multiple exclusions: interstate hazmat in excluded state."
}}
"""

    # Initialize Gemini client
    client = genai.Client(api_key=API_KEY)
    print("Sending requests to Gemini API...")
    
    # Process each record
    results = []
    save_interval = 10  # save every 10 records
    for i, (idx, rec) in enumerate(sampledf.iterrows(), start=1):
        record_dict = rec.to_dict()
        record_json = json.dumps(record_dict, indent=2, default=str)
        userprompt = f"Evaluate this record:\n{record_json}"
        prompt = systemprompt + "\n\n" + userprompt

        print(f"Processing DOT {rec[dot_col]} ({i}/{len(sampledf)})...")

        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            responsetext = response.text.strip()

            # Clean markdown artifacts
            clean_text = re.sub(r"^```(json)?\s*", "", responsetext)
            clean_text = re.sub(r"```$", "", clean_text)

            result = json.loads(clean_text)
            results.append(result)

        except Exception as e:
            print(f"Error processing DOT {rec[dot_col]}: {e}")
            results.append({"dot_number": str(rec[dot_col]), "error": str(e)[:200]})

        # ---- incremental save ----
        if i % save_interval == 0:
            temp_out = os.path.join(
                OUTPUTDIR,
                f"company-fit-results_{MODEL}_{TIMESTAMP}_partial.csv"
            )
            pd.DataFrame(results).to_csv(temp_out, index=False)
            print(f"✅ Saved progress after {i} records → {temp_out}")

    # Final save
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_RESULTS, index=False)
    print(f"\n✅ Final results saved to {OUTPUT_RESULTS}")
    print(f"Successfully processed {len(results_df)} records")

if __name__ == "__main__":
    main()