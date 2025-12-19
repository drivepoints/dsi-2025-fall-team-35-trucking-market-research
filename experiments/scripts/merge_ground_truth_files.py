import pandas as pd

# --- Input paths ---
xlsx_path = "../evaluation/sample-for-annotation-494.xlsx"
csv_path = "../evaluation/ground_truth_506.csv"
output_path = "../evaluation/ground_truth_1000.csv"

# --- Load both files ---
xlsx_df = pd.read_excel(xlsx_path, dtype=str)
csv_df = pd.read_csv(csv_path, dtype=str)

# --- Normalize column names (just in case) ---
xlsx_df.columns = xlsx_df.columns.str.strip().str.lower()
csv_df.columns = csv_df.columns.str.strip().str.lower()

# --- Select only the needed columns ---
needed_cols = ["dot_number", "expert_label"]

xlsx_small = xlsx_df[needed_cols].copy()
csv_small = csv_df[needed_cols].copy()

# --- Combine (494 + 506 = 1000 rows) ---
combined = pd.concat([xlsx_small, csv_small], ignore_index=True)

# --- Remove duplicates (should not occur, but safe) ---
combined = combined.drop_duplicates(subset=["dot_number"], keep="first")

# --- Sort by DOT for neatness ---
combined = combined.sort_values("dot_number").reset_index(drop=True)

# --- Save final 1000-row file ---
combined.to_csv(output_path, index=False)

print("Done! Saved ->", output_path)
print("Final row count:", len(combined))

