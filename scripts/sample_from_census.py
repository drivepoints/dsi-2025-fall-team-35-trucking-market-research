import pandas as pd

# --- File paths ---
census_path = "../data/nov_18_census.csv"
already_annotated_path = "../evaluation/ground_truth_506.csv"
cargo_carried_path = "../data/dot_cargo_carried.csv"
output_path = "../evaluation/ground_truth_494.csv"

# --- Parameters ---
states = ["CA", "TX", "CO", "UT", "WA", "MN", "AZ", "OR", "NM", "ID", "WY", "NE", "KS", "MO"]
sample_size = 494

# --- Load data ---
census_df = pd.read_csv(census_path, dtype=str)
census_df.columns = census_df.columns.str.lower().str.strip()

annotated_df = pd.read_csv(already_annotated_path, dtype=str)

# Load cargo carried data
cargo_df = pd.read_csv(cargo_carried_path, dtype=str)
cargo_df.columns = cargo_df.columns.str.lower().str.strip()

# --- Filter out already annotated DOTs ---
excluded_dots = set(annotated_df["dot_number"].dropna().unique())
filtered_df = census_df[~census_df["dot_number"].isin(excluded_dots)]

# --- Keep only west-of-Mississippi states ---
filtered_df = filtered_df[filtered_df["phy_state"].isin(states)]

# --- Randomly sample ---
sample_df = filtered_df.sample(n=sample_size, random_state=42)

# (1) Merge Cargo Carried using dot_number
sample_df = sample_df.merge(
    cargo_df[["dot_number", "cargo_carried"]],
    on="dot_number",
    how="left"
)

# (2) Add SAFER URL
sample_df["safer_url"] = (
    "https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY"
    "&query_type=queryCarrierSnapshot&query_param=USDOT&query_string="
    + sample_df["dot_number"]
)

# (3) Insert expert_label column (empty)
# Insert as the *4th column after dot_number* = at position dot_idx + 4
dot_idx = sample_df.columns.get_loc("dot_number")

sample_df.insert(dot_idx + 1, "cargo_carried", sample_df.pop("cargo_carried"))
sample_df.insert(dot_idx + 2, "safer_url", sample_df.pop("safer_url"))
sample_df.insert(dot_idx + 3, "expert_label", "")

# --- Save to CSV ---
sample_df.to_csv(output_path, index=False)

print(f"Sampled {len(sample_df)} records to {output_path}")
