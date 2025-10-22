import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from math import sqrt

# --- CONFIG ---
GROUND_TRUTH_FILE = "../llm/validation/ground-truth-100.csv"
LLM_RESULTS_FILE = "../llm/output/company-fit-results_gemini-2.5-flash-lite_20251022_1021.csv"

LABEL_MAPPING = {
    "BAD": 0.2,
    "OK": 0.5,
    "GOOD": 0.7,
    "GREAT": 0.9
}

CATEGORY_ORDER = ["BAD", "OK", "GOOD", "GREAT"]

def map_score_to_label(score):
    if pd.isna(score):
        return "UNKNOWN"
    if score >= 0.8: return "GREAT"
    elif score >= 0.6: return "GOOD"
    elif score >= 0.4: return "OK"
    else: return "BAD"

def margin_of_error(p, n, confidence=0.95):
    z = 1.96 if confidence == 0.95 else 2.58
    return z * sqrt(p * (1 - p) / n)

def main():
    gt = pd.read_csv(GROUND_TRUTH_FILE)
    llm = pd.read_csv(LLM_RESULTS_FILE)

    df = gt.merge(llm, on="dot_number", how="inner", suffixes=("_human", "_llm"))
    print(f"Matched {len(df)} records")

    df["human_score"] = df["expert_label"].map(LABEL_MAPPING)
    df["llm_score"] = df["company_quality_score"]
    df["llm_label"] = df["llm_score"].apply(map_score_to_label)

    # Remove missing data
    df = df.dropna(subset=["human_score", "llm_score"])

    # --- Accuracy ---
    df["exact_match"] = df["expert_label"] == df["llm_label"]
    accuracy = df["exact_match"].mean()
    moe = margin_of_error(accuracy, len(df))

    # --- Adjacent accuracy ---
    def adjacent(row):
        return abs(CATEGORY_ORDER.index(row["expert_label"]) -
                   CATEGORY_ORDER.index(row["llm_label"])) <= 1
    adjacent_accuracy = df.apply(adjacent, axis=1).mean()

    print("\n--- RESULTS ---")
    print(f"Accuracy:     {accuracy:.2%}")
    # print(f"Adjacent Accuracy:  {adjacent_accuracy:.2%}")
    print(f"95% Margin of Error: ±{moe:.2%}")
    print(f"Sample Size: {len(df)}")
    
    # --- Save results to CSV ---
    summary = pd.DataFrame([{
        "model": "gemini-2.5-flash-lite",  # update per run
        "n": len(df),
        "accuracy": accuracy,
        "margin_of_error_95": moe
    }])

    summary_path = "../llm/validation/accuracy-summary.csv"

    # Append if file exists, otherwise create it
    try:
        existing = pd.read_csv(summary_path)
        summary = pd.concat([existing, summary], ignore_index=True)
    except FileNotFoundError:
        pass

    summary.to_csv(summary_path, index=False)
    print(f"\nSummary metrics saved to: {summary_path}")


    # --- Confusion Matrix ---
    cm = pd.crosstab(df["expert_label"], df["llm_label"], normalize="index") * 100
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, cmap="Blues", fmt=".1f", cbar_kws={"label": "%"})
    plt.title("Confusion Matrix (% by Human Label)")
    plt.xlabel("LLM Label")
    plt.ylabel("Human Label")
    plt.tight_layout()
    plt.show()

    # --- Accuracy by Category ---
    cat_acc = df.groupby("expert_label")["exact_match"].mean() * 100
    cat_acc = cat_acc.reindex(CATEGORY_ORDER)

    plt.figure(figsize=(6, 4))
    sns.barplot(
        x=cat_acc.index,
        y=cat_acc.values,
        hue=cat_acc.index,        # assign hue to x variable
        palette="viridis",
        legend=False              # disable redundant legend
    )
    plt.title("Accuracy by Category")
    plt.ylabel("Accuracy (%)")
    plt.ylim(0, 100)
    for i, v in enumerate(cat_acc):
        plt.text(i, v + 2, f"{v:.0f}%", ha="center")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
