import pandas as pd

# --- Load the full 1000-row ground truth ---
df = pd.read_csv("../evaluation/ground_truth_1000.csv", dtype=str)

# Normalize column names and values
df.columns = df.columns.str.strip().str.lower()
df["expert_label"] = df["expert_label"].str.strip().str.upper()

# --- Binary mapping based directly on Zsolt's guidance ---
binary_map = {
    "BAD": "BAD",
    "OK": "GOOD",
    "GOOD": "GOOD",
    "GREAT": "GOOD"
}

# Add binary label column
df["binary_label"] = df["expert_label"].map(binary_map)

# Optional: sanity check for unexpected labels
unexpected = df[df["binary_label"].isna()]
if len(unexpected) > 0:
    print("WARNING: Unexpected labels found:")
    print(unexpected)
else:
    print("All labels mapped successfully.")

# Save final file
df.to_csv("../evaluation/ground_truth_1000_with_binary.csv", index=False)

print("Saved: ../evaluation/ground_truth_1000_with_binary.csv")

