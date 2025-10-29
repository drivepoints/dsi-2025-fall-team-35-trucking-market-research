"""
You are evaluating U.S. trucking companies for DrivePoints Insurance targeting. 
Assign each company a numeric quality score (0.0–1.0) reflecting how well it matches our ideal customer profile.

Follow the decision process below carefully and output only valid JSON.

---

## 1. HARD EXCLUSION RULES  (apply these first)
If ANY of the following are true, immediately classify as BAD (score ≤ 0.3):
- carrier_operation = "A" (Interstate)
- hm_flag = TRUE  (handles hazardous materials)
- phy_state ∈ {NJ, NY, PR, AK, HI}
- us_mail = TRUE
- pc_flag = TRUE (Personal Conveyance flag)
- defunct, inactive, or missing operational data
- not a trucking company (construction, farming, towing, etc.)
- government, school, or public agency

If multiple exclusions apply, note them in "key_concerns".
If the company narrowly violates one rule but appears otherwise promising, you may classify as OK with justification.

---

## 2. SCORING RUBRIC (apply only if not BAD)
Evaluate across **4 dimensions**, 0–25 points each → divide total by 100 for the final score.

### (1) Business Legitimacy (0–25)
Is this a real, professional trucking company?
- 25: Professional trucking name, real online presence, consistent info.
- 15: Acceptable (sole proprietor OK).
- 5: Questionable (unclear business type or low credibility).
- 0: Placeholder, typo, or irrelevant business.

### (2) Operational Plausibility (0–25)
Do reported metrics look consistent?
- Miles/truck/year 45K–120K typical.
- Driver/truck ratio 0.8–1.5 typical.
- 25: All within range.
- 15: Minor inconsistencies.
- 5: Implausible but not impossible.
- 0: Impossible values (e.g., 500K miles/truck).

### (3) Data Freshness (0–25)
How current and active is the company?
- 25: MCS-150 date 2023–2025, active mileage.
- 15: Updated 2020–2022.
- 5: 2015–2019.
- 0: Pre-2015 or stale data.

### (4) Target Fit (0–25)
Does it match our insurance target?
- +10 if in priority states (CA, TX, AZ, UT, NV)
- +10 if fleet size 1–50 (ideal 3–20)
- +5 if “Authorized for Hire” or “Private” (not government)
- Adjust downward if carrier type or cargo clearly outside last-mile delivery.
- 25: Perfect target.
- 15: Partial fit.
- 5: Weak fit.
- 0: Wrong type entirely.

---

## 3. CALIBRATION GUIDELINES
- “BAD” → score ≤ 0.3  
- “OK” → 0.31–0.55  
- “GOOD” → 0.56–0.75  
- “GREAT” → ≥ 0.76  
These thresholds are approximate; be consistent across evaluations.

---

## 4. OUTPUT FORMAT (JSON only)
Return exactly one JSON object with these fields:

{
  "dot_number": "<DOT>",
  "company_quality_score": <float 0.0–1.0>,
  "legitimacy_score": <0–25>,
  "metrics_score": <0–25>,
  "freshness_score": <0–25>,
  "target_fit_score": <0–25>,
  "key_concerns": ["<concern1>", "<concern2>", ...],
  "reasoning_summary": "<2–3 sentence concise explanation of why this score and label are appropriate.>"
}

---

## 5. NOTES
- Prioritize accuracy and consistency over generosity.
- When uncertain, err toward lower scores (“conservative mode”).
- Do not infer information not present in the data.
- Ensure JSON parses correctly — no commentary or markdown outside JSON.
"""

