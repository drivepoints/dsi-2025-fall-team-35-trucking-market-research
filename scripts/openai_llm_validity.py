import os
import random
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# =============================
# COST ESTIMATES
# =============================
# Based on experiments, it costs about $0.20 per 100 records reviewed by the LLM.

# =============================
# CONFIGURATION
# =============================
INPUT_FILE = "../data/transportation_data_20250917_222245.parquet"
SAMPLE_SIZE = 10
OUTPUT_FILE = "../llm/output/validity_sample_results.csv"
MODEL = "o3-mini"  # Adjust as needed
SEED = 27  # For reproducibility

# =============================
# MAIN SCRIPT
# =============================

def main():
    # Check if the output directory exists, and create it if it doesn't
    output_dir = os.path.dirname(OUTPUT_FILE)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    # Load environment variables (API key)
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Read dataset
    df = pd.read_parquet(INPUT_FILE)
    print(f"Loaded {len(df)} records from {INPUT_FILE}")

    # Random sample
    sample_df = df.sample(n=SAMPLE_SIZE, random_state=SEED)
    print(f"Sampled {len(sample_df)} records for LLM evaluation")

    # Prepare prompt for structured evaluation
    system_prompt = """You are a data quality analyst evaluating the VALIDITY of trucking company data records.

For each record, assess the **trustworthiness** of the data using these criteria:
- Company name plausibility (typos, placeholders, fake text like "ABC Company")
- Plausibility of metrics (e.g., 150,000 miles/truck/year is reasonable; 850,000 is not)
- Consistency between related fields (e.g., 2 drivers but 50 trucks is inconsistent)
- Format issues (emails, phone numbers, or addresses that look invalid)

Return your judgment as structured JSON with the following schema:
[
  {
    "record_id": <index or dot_number>,
    "validity_score": <float between 0 and 1>,
    "issues": "<short bullet summary of detected problems or 'None'>",
    "summary_comment": "<2-sentence human-readable summary>"
  }
]

Scoring guidelines:
- 1.0 = fully valid, realistic, consistent
- 0.5 = minor issues or plausible but slightly off
- 0.0 = clearly invalid, placeholder, or implausible

Output only valid JSON.
"""

    # Construct records for the LLM
    records = sample_df.to_dict(orient="records")

    user_prompt = "Evaluate the following records for data validity:\n\n"
    for rec in records:
        user_prompt += f"{rec}\n"

    # Send to OpenAI
    print("Sending request to OpenAI API...")
    response = client.chat.completions.create(
        model=MODEL,
        # temperature=TEMPERATURE, # temperature is not supported by o3-mini
        seed=SEED,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    response_text = response.choices[0].message.content

    # Attempt to parse structured JSON response
    import json
    try:
        results = json.loads(response_text)
    except json.JSONDecodeError:
        print("Warning: LLM did not return valid JSON. Saving raw output instead.")
        results = [{"raw_response": response_text}]

    # Save results
    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print(f"Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

