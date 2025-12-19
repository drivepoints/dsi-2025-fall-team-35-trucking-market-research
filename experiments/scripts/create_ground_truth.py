import pandas as pd

# --- Input file paths ---
path_100 = "../evaluation/sample-for-annotation-100.csv"
path_400 = "../evaluation/sample-for-annotation-400.csv"

# --- Load files (only needed columns) ---
df_100 = pd.read_csv(path_100, usecols=["dot_number", "expert_label"])
df_400 = pd.read_csv(path_400, usecols=["dot_number", "expert_label"])

# --- Combine both sets ---
df = pd.concat([df_100, df_400], ignore_index=True)

# --- Add 3 manual expert annotations ---
extra = pd.DataFrame([
    {"dot_number": 3493401, "expert_label": "GOOD"},  # Amazon package delivery
    {"dot_number": 759281,  "expert_label": "BAD"},   # Corporate coach charter
    {"dot_number": 2030937, "expert_label": "GOOD"}   # Restoration company
])

df = pd.concat([df, extra], ignore_index=True)

# --- Clean up ---
df = (
    df.drop_duplicates(subset="dot_number", keep="last")
      .sort_values("dot_number")
      .reset_index(drop=True)
)

# --- Save final clean file ---
output_path = "../evaluation/ground_truth_500_final.csv"
df.to_csv(output_path, index=False)

print(f"Saved final ground truth file: {output_path}")
print(f"Total records: {len(df)}")

