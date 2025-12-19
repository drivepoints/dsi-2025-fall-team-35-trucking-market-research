import pandas as pd
import numpy as np
import re
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------
KEY_FIELDS = [
    "legal_name", "dba_name", "carrier_operation", "add_date",
    "email_address", "telephone", "phy_street", "phy_city",
    "phy_state", "phy_zip", "driver_total", "mcs150_date",
    "mcs150_mileage", "mcs150_mileage_year",
    "recent_mileage", "recent_mileage_year"
]

SAMPLE_SIZE = 500
WEIGHTS = {"completeness": 1/3, "validity": 1/3, "timeliness": 1/3}

# -----------------------------
# METRIC FUNCTIONS
# -----------------------------

def show_completeness_examples(df, n=10):
    missing_vals = ["", " ", "NA", "N/A", "None", None]
    print("\n--- Completeness Failures (examples) ---")
    for col in KEY_FIELDS:
        bad = df[df[col].isin(missing_vals)][col].head(n)
        if not bad.empty:
            print(f"{col}: {bad.to_list()}")

def calc_completeness(df):
    """Percentage of non-missing values in key fields."""
    missing_vals = ["", " ", "NA", "N/A", "None", None]
    completeness = df[KEY_FIELDS].apply(
        lambda col: col.isin(missing_vals).mean()
    )
    return 1 - completeness.mean()

def calc_structural_validity(df, show_examples=True):
    checks = []
    if show_examples: print("\n--- Validity Failures (examples) ---")

    if "email_address" in df.columns:
        email_valid = df["email_address"].fillna("").str.match(r"[^@]+@[^@]+\.[^@]+")
        checks.append(email_valid.mean())
        if show_examples:
            print("Invalid emails:", df.loc[~email_valid, "email_address"].dropna().unique()[:10])

    if "telephone" in df.columns:
        phone_valid = df["telephone"].fillna("").str.match(r"^\+?\d{7,15}$")
        checks.append(phone_valid.mean())
        if show_examples:
            print("Invalid phones:", df.loc[~phone_valid, "telephone"].dropna().unique()[:10])

    if "phy_zip" in df.columns:
        zip_valid = df["phy_zip"].fillna("").astype(str).str.match(r"^\d{5}$")
        checks.append(zip_valid.mean())
        if show_examples:
            print("Invalid zips:", df.loc[~zip_valid, "phy_zip"].dropna().unique()[:10])

    return np.mean(checks) if checks else 0

def calc_timeliness(df, reference_date=None, show_examples=True):
    if reference_date is None:
        reference_date = datetime.today()
    current_year = reference_date.year
    scores = []
    if show_examples: print("\n--- Timeliness Failures (examples) ---")

    # mcs150_date
    if "mcs150_date" in df.columns:
        mcs = pd.to_datetime(df["mcs150_date"].replace("None", pd.NA),
                             format="%d-%b-%y", errors="coerce")
        if mcs.notna().any():
            avg_age_days = (reference_date - mcs.dropna()).dt.days.mean()
            scores.append(np.clip(1 - (avg_age_days / 730), 0, 1))
            if show_examples:
                print("Old mcs150_date:", mcs[mcs.notna() & ((reference_date - mcs).dt.days > 730)].head(10).to_list())

    # add_date
    if "add_date" in df.columns:
        adds = pd.to_datetime(df["add_date"].replace("None", pd.NA),
                              format="%d-%b-%y", errors="coerce")
        if adds.notna().any():
            avg_age_days = (reference_date - adds.dropna()).dt.days.mean()
            scores.append(np.clip(1 - (avg_age_days / 1825), 0, 1))
            if show_examples:
                print("Old add_date:", adds[adds.notna() & ((reference_date - adds).dt.days > 1825)].head(10).to_list())

    # recent_mileage_year
    if "recent_mileage_year" in df.columns:
        mileage_years = pd.to_numeric(df["recent_mileage_year"], errors="coerce").replace(0, pd.NA)
        if mileage_years.notna().any():
            avg_diff = (current_year - mileage_years.dropna()).mean()
            scores.append(np.clip(1 - (avg_diff / 5), 0, 1))
            if show_examples:
                print("Old recent_mileage_year:", mileage_years[mileage_years.notna() & (current_year - mileage_years > 5)].head(10).to_list())

    # mcs150_mileage_year
    if "mcs150_mileage_year" in df.columns:
        mileage_years = pd.to_numeric(df["mcs150_mileage_year"], errors="coerce")
        if mileage_years.notna().any():
            avg_diff = (current_year - mileage_years.dropna()).mean()
            scores.append(np.clip(1 - (avg_diff / 5), 0, 1))
            if show_examples:
                print("Old mcs150_mileage_year:", mileage_years[mileage_years.notna() & (current_year - mileage_years > 5)].head(10).to_list())

    return np.mean(scores) if scores else 0

def get_random_sample(df, month_str, n=SAMPLE_SIZE):
    """Draw reproducible random sample based on month string."""
    seed = int.from_bytes(month_str.encode(), "little") % (2**32 - 1)
    return df.sample(n=n, random_state=seed)

def calc_dqs(completeness, validity, timeliness, weights=WEIGHTS):
    return (weights["completeness"] * completeness +
            weights["validity"] * validity +
            weights["timeliness"] * timeliness)

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def run_monthly_metric(path, month_str):
    # Load parquet 
    df = pd.read_parquet(path)

    completeness = calc_completeness(df)
    show_completeness_examples(df)
    validity = calc_structural_validity(df, show_examples=True)
    timeliness = calc_timeliness(df, show_examples=True)

    dqs = calc_dqs(completeness, validity, timeliness)

    print(f"Month: {month_str}")
    print(f"Completeness: {completeness:.3f}")
    print(f"Validity: {validity:.3f}")
    print(f"Timeliness: {timeliness:.3f}")
    print(f"Overall DQS: {dqs:.3f}")

    # Save sample for semantic checks
    sample = get_random_sample(df, month_str, SAMPLE_SIZE)
    sample.to_csv(f"sample_{month_str}.csv", index=False)

    return {
        "month": month_str,
        "completeness": completeness,
        "validity": validity,
        "timeliness": timeliness,
        "dqs": dqs
    }

if __name__ == "__main__":
    # Example: run on your dataset
    results = run_monthly_metric("../data/transportation_data_20250917_222245.parquet", "2025-09")