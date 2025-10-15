import os
import pandas as pd
import json
import ast
import re
from dotenv import load_dotenv
from google import genai
from datetime import datetime

# --- CONFIG ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

INPUTFILE = "../data/transportation_data_20251013_135544.parquet"
SAMPLESIZE = 10
SEED = 99
MODEL = "gemini-2.5-flash-lite"

OUTPUTDIR = "../quality-scores"
OUTPUT_SAMPLE = os.path.join(OUTPUTDIR, "pilot-gemini-validity-sample-records.csv")
OUTPUT_RESULTS = os.path.join(OUTPUTDIR, "pilot-gemini-validity-sample-results.csv")

def parse_file_date(filename):
    match = re.search(r'(\\d{8})_\\d{6}\\.parquet$', filename)
    if match:
        extracted_date = match.group(1)
        parsed_date = datetime.strptime(extracted_date, "%Y%m%d")
        return parsed_date.strftime("%B %d, %Y")  # e.g. "October 13, 2025"
    return "Unknown"

# --- MAIN SCRIPT ---
def main():
    # Ensure output directory exists
    os.makedirs(OUTPUTDIR, exist_ok=True)

    # Load data
    df = pd.read_parquet(INPUTFILE)
    print(f"Loaded {len(df)} records from {INPUTFILE}")

    dot_col = "dot_number"
    print(f"Using column '{dot_col}' as the record identifier.")

    # Sample records reproducibly
    sampledf = df.sample(n=SAMPLESIZE, random_state=SEED)
    print(f"Sampled {len(sampledf)} records for LLM evaluation")

    # Save the sampled records before evaluation
    sampledf.to_csv(OUTPUT_SAMPLE, index=False)
    print(f"Sampled records saved to {OUTPUT_SAMPLE}")
    
    # Parse date from filename and include it in the prompt
    today_str = datetime.now().strftime("%B %d, %Y")
    file_date_str = parse_file_date(INPUTFILE)
    date_context = (
        f"\n\nThe dataset was created on {file_date_str}. "
        f"Today's date is {today_str}. "
        "Use this date context for recency checks."
    )

    # Prepare Gemini LLM prompt
    systemprompt = (
    f"""
    You are a data quality analyst evaluating the VALIDITY of trucking company data records.

    For each record, assess the trustworthiness of the data using these criteria:
    - Company name plausibility (typos, placeholders, fake text like 'ABC Company')
    - Plausibility of metrics (e.g., 150,000 miles/truck/year is reasonable; 850,000 is not)
    - Consistency between related fields (e.g., 2 drivers but 50 trucks is inconsistent)
    - Format issues (emails, phone numbers, or addresses that look invalid)

    Return your judgment as valid JSON using this schema:
    {{'dot_number': integer, 'legal_name': string, 'phy_state': two-letter state code string, 'validity_score': float [0,1], 'issues': string or None, 'summary_comment': string}}

    Scoring guidelines:
    - 1.0: fully valid, realistic, consistent
    - 0.5: minor issues or plausible but slightly off
    - 0.0: clearly invalid, placeholder, or implausible

    Return only valid JSON.
    {date_context}
    """
    )

    # Build record text for prompt
    userprompt = "Evaluate the following records for data validity:\n"
    for _, rec in sampledf.iterrows():
        record_text = rec.to_dict()
        userprompt += f"{record_text}\n"

    prompt = systemprompt + "\n\n" + userprompt

    print("Sending request to Gemini API...")

    # Initialize Gemini client
    client = genai.Client(api_key=API_KEY)

    # Send prompt to Gemini model
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    responsetext = response.text
    print(responsetext)

    # --- Clean the response text before parsing ---
    clean_text = responsetext.strip()

    # Remove Markdown code fences (```json ... ``` or ```)
    clean_text = re.sub(r"^```(json)?\s*", "", clean_text)
    clean_text = re.sub(r"```$", "", clean_text)
    
    # Parse or save raw output
    try:
        results = json.loads(clean_text)
        pd.DataFrame(results).to_csv(OUTPUT_RESULTS, index=False)
        print(f"Results saved to {OUTPUT_RESULTS}")
    except json.JSONDecodeError:
        try:
            results = ast.literal_eval(clean_text)
        except Exception:
            results = None
            print("Warning: Gemini did not return valid JSON. Saving raw output instead.")
            pd.DataFrame([{"raw_response": responsetext}]).to_csv(OUTPUT_RESULTS, index=False)

if __name__ == "__main__":
    main()
