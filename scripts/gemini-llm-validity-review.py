import os
import random
import pandas as pd
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
INPUTFILE = "../data/transportation_data_20251013_135544.parquet"  # Use same input
SAMPLESIZE = 10
OUTPUTFILE = "../quality-scores/gemini-validity-sample-results.csv"
MODEL = "gemini-2.0-flash-lite-001"
SEED = 27

def main():
    # Check and create output directory
    outputdir = os.path.dirname(OUTPUTFILE)
    if not os.path.exists(outputdir):
        os.makedirs(outputdir)
        print(f"Created directory {outputdir}")

    # Load data
    df = pd.read_parquet(INPUTFILE)
    print(f"Loaded {len(df)} records from {INPUTFILE}")

    # Sample records for LLM evaluation
    sampledf = df.sample(n=SAMPLESIZE, random_state=SEED)
    print(f"Sampled {len(sampledf)} records for LLM evaluation")

    # Prepare Gemini LLM prompt
    systemprompt = (
        "You are a data quality analyst evaluating the VALIDITY of trucking company data records. "
        "For each record, assess the trustworthiness of the data using these criteria:\n"
        "- Company name plausibility (typos, placeholders, fake text like ABC Company)\n"
        "- Plausibility of metrics (e.g., 150,000 miles/truck/year is reasonable; 850,000 is not)\n"
        "- Consistency between related fields (e.g., 2 drivers but 50 trucks is inconsistent)\n"
        "- Format issues (emails, phone numbers, or addresses that look invalid)\n\n"
        "Return your judgment as valid JSON using this schema:\n"
        "{'recordid': index or dotnumber, 'validityscore': float [0,1], 'issues': string or None, 'summarycomment': string}\n"
        "Scoring guidelines:\n"
        "- 1.0: fully valid, realistic, consistent\n"
        "- 0.5: minor issues or plausible but slightly off\n"
        "- 0.0: clearly invalid, placeholder, or implausible\n"
        "**Return only valid JSON.**"
    )

    records = sampledf.to_dict(orient="records")
    userprompt = "Evaluate the following records for data validity:\n"
    prompt = systemprompt + "\n\n" + userprompt
    for rec in records:
        userprompt += f"{rec}\n"

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

    # Attempt to parse structured JSON response. Save to CSV.
    try:
        results = json.loads(responsetext)
        pd.DataFrame(results).to_csv(OUTPUTFILE, index=False)
        print(f"Results saved to {OUTPUTFILE}")
    except json.JSONDecodeError:
        print("Warning: Gemini did not return valid JSON. Saving raw output instead.")
        results = {"rawresponse": responsetext}
        pd.DataFrame([{"raw_response": responsetext}]).to_csv(OUTPUTFILE, index=False)

if __name__ == "__main__":
    main()
