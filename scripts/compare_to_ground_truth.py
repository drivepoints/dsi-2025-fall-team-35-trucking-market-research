#!/usr/bin/env python3
"""
compare_to_ground_truth.py
Compare model outputs to expert-labeled ground truth using dot_number as the key.

Inputs:
  ../evaluation/log_reg_baseline.csv   (must contain: dot_number, company_fit_score)
  ../evaluation/ground_truth_503.csv        (must contain: dot_number, expert_label)
Outputs:
  Prints Accuracy, Balanced Accuracy, Precision, Recall, and F1 Score.
"""

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

# --- Load data ---
pred_path = "../evaluation/log_reg_baseline.csv"
gt_path = "../evaluation/ground_truth_503.csv"

pred_df = pd.read_csv(pred_path)
gt_df = pd.read_csv(gt_path)

# --- Merge on dot_number ---
df = pd.merge(pred_df, gt_df, on="dot_number", how="inner")

# --- Prepare binary labels ---
# Map expert labels to binary values: GOOD/GREAT → 1, OK/BAD → 0
def encode_label(label):
    label = str(label).strip().upper()
    if label in {"GOOD", "GREAT"}:
        return 1
    elif label in {"OK", "BAD"}:
        return 0
    else:
        return None

df["true_label"] = df["expert_label"].apply(encode_label)

# --- Threshold model scores to predicted labels ---
# Default threshold = 0.5; adjust if desired.
df["pred_label"] = (df["company_fit_score"] >= 0.5).astype(int)

# --- Compute metrics ---
y_true = df["true_label"]
y_pred = df["pred_label"]

metrics = {
    "Accuracy": accuracy_score(y_true, y_pred),
    "Balanced Accuracy": balanced_accuracy_score(y_true, y_pred),
    "Precision": precision_score(y_true, y_pred, zero_division=0),
    "Recall": recall_score(y_true, y_pred, zero_division=0),
    "F1 Score": f1_score(y_true, y_pred, zero_division=0),
}

# --- Display results ---
print("\nModel Evaluation Metrics (n = {})".format(len(df)))
for k, v in metrics.items():
    print(f"{k:>20}: {v:.3f}")

# Optional: Save merged comparison for auditing
df.to_csv("../evaluation/comparison_output.csv", index=False)
print("\nSaved joined comparison to ../evaluation/comparison_output.csv")

