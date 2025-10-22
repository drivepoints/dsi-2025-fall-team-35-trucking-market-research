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
MODEL = "gemini-2.5-flash"

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
You are evaluating trucking companies for DrivePoints insurance targeting. Score each company 0.0-1.0 based on how well they match our ideal customer profile.

## Context
- Target: Active Class 6 trucking (last-mile, furniture delivery), 1-50 trucks, priority states (CA, TX, AZ, UT, NV)
- Avoid: Defunct companies, self-insured giants (FedEx/UPS), non-trucking businesses, stale data
- Date context: {date_context}

## Scoring Method (4 dimensions, 25 points each → divide by 100):

### 1. Business Legitimacy (0-25)
Is this a real trucking company?
- 25: Professional name, clear trucking operation
- 15: Acceptable (personal name for sole proprietor OK)
- 5: Questionable (typos, unclear business type)
- 0: Placeholder text ("ABC Company"), non-trucking (aquariums, construction-only)

### 2. Operational Plausibility (0-25)
Do the numbers make sense?
- Miles/truck/year: Normal = 45K-120K (flag if >200K or <5K)
- Driver/truck ratio: Normal = 0.8-1.5 (flag extremes like 2 drivers/50 trucks)
- 25: All metrics reasonable and consistent
- 15: Minor issues
- 5: Major implausibility (500K miles/truck)
- 0: Multiple impossible values

### 3. Data Freshness (0-25)
Is the company active?
- mcs150_date recency: 2023-2025 ideal, pre-2020 concerning, pre-2015 major red flag
- recent_mileage: Should be >0 and align with fleet size
- 25: Updated last 2 years, active mileage
- 15: Updated 2-4 years ago
- 5: Stale (>5 years)
- 0: Ancient (>10 years) or zero activity

### 4. Target Fit (0-25)
Does this match our ideal customer?
- Priority state (CA/TX/AZ/UT/NV): +10
- Fleet size 1-50 trucks (sweet spot 3-20): +10
- Authorized for hire or private (not government): +5
- 25: Perfect match
- 15: Meets 2-3 criteria
- 5: Meets 1 criterion
- 0: Wrong profile entirely

**Final Score = Total Points / 100**

## Output (JSON only):
{{
  "dot_number": "<DOT>",
  "company_quality_score": <0.0-1.0>,
  "legitimacy_score": <0-25>,
  "metrics_score": <0-25>,
  "freshness_score": <0-25>,
  "target_fit_score": <0-25>,
  "key_concerns": ["<concern 1>", "<concern 2>"],
  "reasoning_summary": "<2-3 sentences>"
}}
"""

    # Initialize Gemini client
    client = genai.Client(api_key=API_KEY)
    print("Sending requests to Gemini API...")
    
    # Process each record
    results = []
    for idx, rec in sampledf.iterrows():
        record_dict = rec.to_dict()
        record_json = json.dumps(record_dict, indent=2, default=str)
        
        userprompt = f"Evaluate this record:\n{record_json}"
        prompt = systemprompt + "\n\n" + userprompt
        
        print(f"Processing DOT {rec[dot_col]}...")
        
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt
            )
            
            responsetext = response.text.strip()
            
            # Clean markdown
            clean_text = re.sub(r"^```(json)?\s*", "", responsetext)
            clean_text = re.sub(r"```$", "", clean_text)
            
            result = json.loads(clean_text)
            results.append(result)
            
        except Exception as e:
            print(f"Error processing DOT {rec[dot_col]}: {e}")
            results.append({"dot_number": str(rec[dot_col]), "error": str(e)[:200]})
    
    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_RESULTS, index=False)
    print(f"\nResults saved to {OUTPUT_RESULTS}")
    print(f"Successfully processed {len(results_df)} records")

if __name__ == "__main__":
    main()