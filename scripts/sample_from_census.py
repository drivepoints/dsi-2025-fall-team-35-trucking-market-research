import pandas as pd

# --- File paths ---
census_path = "../data/nov_5_census.csv"
annotated_path = "../data/sample-for-annotation-100-zsolt.csv"
output_path = "../data/sample-for-annotation-400-west.csv"

# --- Parameters ---
states = ["CA", "TX", "CO", "UT", "WA", "MN", "AZ", "OR", "NM", "ID", "WY", "NE", "KS", "MO"]
sample_size = 400

# --- Load data ---
census_df = pd.read_csv(census_path, dtype=str)
census_df.columns = census_df.columns.str.lower().str.strip()
annotated_df = pd.read_csv(annotated_path, dtype=str)

# --- Filter out already annotated DOTs ---
excluded_dots = set(annotated_df["dot_number"].dropna().unique())
filtered_df = census_df[~census_df["dot_number"].isin(excluded_dots)]

# --- Keep only west-of-Mississippi states ---
filtered_df = filtered_df[filtered_df["phy_state"].isin(states)]

# --- Randomly sample 400 ---
sample_df = filtered_df.sample(n=sample_size, random_state=42)

# --- Save to CSV ---
sample_df.to_csv(output_path, index=False)

print(f"Sampled {len(sample_df)} records to {output_path}")
