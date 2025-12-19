import pandas as pd

base_path = "../data/sample-for-annotation-400.csv"
cargo_path = "../data/enriched_400_safer_snapshot.csv"
output_path = "../data/sample-for-annotation-400-cargo-added.csv"

# Load both
base = pd.read_csv(base_path, dtype=str)
cargo = pd.read_csv(cargo_path, dtype=str)

# Normalize column names
base.columns = base.columns.str.lower()
cargo.columns = cargo.columns.str.lower()

# Merge on dot_number
merged = base.merge(cargo, on="dot_number", how="left")

# Rename cargo_types → cargo_carried (for clarity)
if "cargo_types" in merged.columns:
    merged = merged.rename(columns={"cargo_types": "cargo_carried"})

merged.to_csv(output_path, index=False)
print(f"✅ Saved merged dataset with all columns to {output_path}")
