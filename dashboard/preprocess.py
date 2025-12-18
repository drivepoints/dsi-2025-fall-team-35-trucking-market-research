"""
Preprocessing module that runs in a standalone fashion to prepare data.

This module is called as a subprocess from the Streamlit app to perform
data extraction, transformation, and loading (ETL) tasks. It handles
downloading Census data, transforming it, and preparing it for analysis.
"""

import sys
from dashboard import etl
from dashboard.utils import data_path_for_version


def preprocess(version):
    """
    Preprocess the dataset for the given version.

    Args:
        version (str): The version of the dataset to process.

    Returns:
        str. It merely guarantees that a data file will be available for
        loading by the main app after it completes.
    """

    data_path = data_path_for_version(version)
    ## Steps:

    ## 0. Download

    df = etl.import_census_data(version)

    ## 1. Transform Data

    df = etl.transform_data(df)

    ## 2. Geoprocess?

    ## 3. Add fit scores.

    ## 4. Add cargo categories.

    df = etl.add_cargo_categories(df)

    ## 5. Add insurance.

    # insurance data cleaning notebook

    ## 6. Add FARS/CRSS.

    # fars crss combiner notebook

    ## 7. Add DQS.
    # """
    # Load the master parquet file and perform all transformations that are
    # independent of user interaction (run once per session, then cached).
    #
    # This function:
    # - Normalizes year-like columns so they display cleanly as year
    # strings.
    # - Maps the ML model score ('ml_score') into 'company_fit_score' and sorts by that score.
    # - Reorders columns so key identification/contact fields appear first.
    # - Merges in any previously saved prospect status information from
    #   STATUS_PATH, if that file exists.
    # """
    #
    # # Normalize DQS (data quality score) if present
    # # Stored as a numeric column in [0, 1] with non-numeric values coerced to NaN
    # if "dqs" in df.columns:
    #     df["dqs"] = pd.to_numeric(df["dqs"], errors="coerce")
    #
    #
    # # Map ML model score to 'company_fit_score' used throughout the app
    # if "ml_score" in df.columns:
    #     df["company_fit_score"] = pd.to_numeric(
    #         df["ml_score"], errors="coerce"
    #     )
    # else:
    #     # Fallback: if ml_score is missing, keep the column so downstream code doesn't break
    #     df["company_fit_score"] = np.nan
    #
    # # Move key identification and contact columns to the front
    # display_columns = [
    #     "dot_number", "legal_name", "company_fit_score",
    #     "email_address", "telephone",
    # ]
    # rest = [c for c in df.columns if c not in display_columns]
    # df = df[display_columns + rest]
    #
    # # Sort once by 'company_fit_score' so "top companies" is well defined
    # df = df.sort_values("company_fit_score", ascending=False)
    #
    # # ----------------------------------------------------------
    # # Attach persisted 'prospect_status' from STATUS_PATH (if any)
    # # ----------------------------------------------------------
    #
    # if os.path.exists(STATUS_PATH):
    #     try:
    #         status_df = pd.read_parquet(STATUS_PATH)
    #         status_df["dot_number"] = status_df["dot_number"].astype(str)
    #
    #         # Ensure exactly one 'prospect_status' per DOT; latest record wins
    #         status_df = (
    #             status_df[["dot_number", "prospect_status"]]
    #             .dropna(subset=["dot_number"])
    #             .drop_duplicates(subset=["dot_number"], keep="last")
    #         )
    #
    #         # Merge saved statuses into the main DataFrame
    #         df = df.merge(
    #             status_df,
    #             on="dot_number",
    #             how="left",
    #             suffixes=("", "_saved"),
    #         )
    #
    #         # If merged file provides a saved status, use it; otherwise apply default
    #         if "prospect_status_saved" in df.columns:
    #             df["prospect_status"] = df["prospect_status_saved"].fillna(
    #                 df.get("prospect_status", "Not Contacted")
    #             )
    #             df.drop(columns=["prospect_status_saved"], inplace=True)
    #         else:
    #             if "prospect_status" not in df.columns:
    #                 df["prospect_status"] = "Not Contacted"
    #
    #     except Exception as e:
    #         # If the status file cannot be read (missing/corrupted), ensure
    #         # a 'prospect_status' column still exists with a default value
    #         if "prospect_status" not in df.columns:
    #             df["prospect_status"] = "Not Contacted"
    # else:
    #     # If there is no status file yet, initialize 'prospect_status' with a default
    #     if "prospect_status" not in df.columns:
    #         df["prospect_status"] = "Not Contacted"
    #
    # return df

    df.write_parquet(data_path)

    return "Preprocessing complete."


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: preprocess.py <version>")
        sys.exit(1)

    preprocess(sys.argv[1])
