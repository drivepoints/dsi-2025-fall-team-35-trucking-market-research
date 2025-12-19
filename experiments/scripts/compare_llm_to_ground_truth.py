import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from math import sqrt
from sklearn.metrics import classification_report, balanced_accuracy_score


# --- CONFIG ---
GROUND_TRUTH_FILE = "../llm/validation/ground-truth-zsolt.csv"
LLM_RESULTS_FILE = "../llm/output/company-fit-results_gemini-2.5-pro_20251027_2040.csv"

LABEL_MAPPING = {
    "BAD": 0.2,
    "OK": 0.5,
    "GOOD": 0.7,
    "GREAT": 0.9
}

CATEGORY_ORDER = ["BAD", "OK", "GOOD", "GREAT"]
BINARY_ORDER = ["bad", "good"]

def margin_of_error(p, n, confidence=0.95):
    z = 1.96 if confidence == 0.95 else 2.58
    return z * sqrt(p * (1 - p) / n)

def map_to_binary(label):
    """Map LLM or human labels to binary: GOOD/GREAT → good, BAD/OK → bad."""
    if isinstance(label, str):
        label_upper = label.strip().upper()
        if label_upper in ["GOOD", "GREAT"]:
            return "good"
        elif label_upper in ["BAD", "OK"]:
            return "bad"
    return "unknown"

def main():
    # --- Load Data ---
    gt = pd.read_csv(GROUND_TRUTH_FILE)
    llm = pd.read_csv(LLM_RESULTS_FILE)

    # Auto-detect whether LLM output contains company_quality_score or classification
    if "classification" in llm.columns:
        print("Detected binary LLM output with classification column.")
        llm["llm_label"] = llm["classification"].str.upper()
        llm["llm_score"] = np.where(llm["llm_label"] == "GOOD", 0.8, 0.2)
    else:
        print("Detected numeric LLM output; using score thresholds.")
        llm["llm_label"] = llm["company_quality_score"].apply(
            lambda x: "GOOD" if x >= 0.55 else "BAD"
        )
        llm["llm_score"] = llm["company_quality_score"]

    # --- Merge and map ---
    df = gt.merge(llm, on="dot_number", how="inner", suffixes=("_human", "_llm"))
    print(f"Matched {len(df)} records")

    df["human_score"] = df["expert_label"].map(LABEL_MAPPING)
    df["human_binary"] = df["expert_label"].apply(map_to_binary)
    df["llm_binary"] = df["llm_label"].apply(map_to_binary)

    df = df.dropna(subset=["human_binary", "llm_binary"])
    print(f"After dropping missing: {len(df)} records remain")

    # --- Binary Accuracy ---
    df["binary_match"] = df["human_binary"] == df["llm_binary"]
    binary_accuracy = df["binary_match"].mean()
    binary_moe = margin_of_error(binary_accuracy, len(df))

    mismatches = df[df["binary_match"] == False]
    print(f"\nFound {len(mismatches)} binary mismatches out of {len(df)} total records.")
    if not mismatches.empty:
        print("\n--- Sample Mismatches ---")
        print(
            mismatches[
                ["dot_number", "expert_label", "llm_label", "human_binary", "llm_binary"]
            ]
            .head(10)
            .to_string(index=False)
        )

    # --- Results ---
    print("\n--- RESULTS ---")
    print(f"Binary Accuracy (GOOD/GREAT vs BAD/OK): {binary_accuracy:.2%} ±{binary_moe:.2%}")
    print(f"Sample Size: {len(df)}")
    print(classification_report(df["human_binary"], df["llm_binary"], digits=2))
    print("Balanced accuracy:", balanced_accuracy_score(df["human_binary"], df["llm_binary"]))

    # --- Binary Confusion Matrix ---
    cm_bin = pd.crosstab(df["human_binary"], df["llm_binary"], normalize="index") * 100
    cm_bin = cm_bin.reindex(index=BINARY_ORDER, columns=BINARY_ORDER, fill_value=0)

    plt.figure(figsize=(4, 3))
    sns.heatmap(cm_bin, annot=True, cmap="Greens", fmt=".1f", cbar_kws={"label": "%"})
    plt.title("Binary Confusion Matrix (% by Human Label)\n(GOOD/GREAT vs BAD/OK)")
    plt.xlabel("LLM Predicted (Binary)")
    plt.ylabel("Human (Binary Ground Truth)")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.show()

    # --- Binary Accuracy Bar Chart ---
    bin_acc = df.groupby("human_binary")["binary_match"].mean() * 100
    bin_acc = bin_acc.reindex(BINARY_ORDER)

    plt.figure(figsize=(4, 3))
    sns.barplot(x=bin_acc.index, y=bin_acc.values, hue=bin_acc.index, palette="Greens", legend=False)
    plt.title("Binary Accuracy by Class")
    plt.ylabel("Accuracy (%)")
    plt.ylim(0, 100)
    for i, v in enumerate(bin_acc):
        plt.text(i, v + 2, f"{v:.0f}%", ha="center")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
