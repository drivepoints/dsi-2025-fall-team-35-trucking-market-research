import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import json
import os
import plotly.graph_objects as go

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------
st.set_page_config(
    page_title="DrivePoints Potential Customer Dashboard",
    layout="wide",
)

# ------------------------------------------------------------------
# Compact HTML table styling for the preview at the bottom
# ------------------------------------------------------------------
compact_table_css = """
<style>
table.dataframe {
    border-collapse: collapse !important;
    border-spacing: 0 !important;
    margin: 0 !important;
    width: 100%;
    font-size: 15px !important;
}
table.dataframe thead th {
    text-align: left !important;
    background-color: rgba(255, 255, 255, 0.12) !important;
    padding-top: 10px !important;
    padding-bottom: 10px !important;
    padding-left: 8px !important;
    padding-right: 8px !important;
    line-height: 1.3 !important;
    white-space: nowrap !important;
    font-weight: 600 !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.18) !important;
}
table.dataframe tbody td {
    padding-top: 6px !important;
    padding-bottom: 6px !important;
    padding-left: 8px !important;
    padding-right: 8px !important;
    line-height: 1.25 !important;
    white-space: nowrap !important;
}
table.dataframe tbody tr {
    background-color: transparent !important;
}
table.dataframe tbody tr + tr td {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}
</style>
"""
st.markdown(compact_table_css, unsafe_allow_html=True)

st.title("🚚 DrivePoints Potential Customer Dashboard")
st.markdown(
    "Preview of transportation companies, ranked, with easy access to contacts and state trends."
)

DATA_PATH = "master_file.parquet"
STATUS_PATH = "prospect_status.parquet"  # Path to a small overlay file that stores prospect status edits


# ------------------------------------------------------------------
# Data loading and one-time transformations
# ------------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """
    Load the master parquet file and perform all transformations that are
    independent of user interaction (run once per session, then cached).

    This function:
    - Standardizes column names to lowercase.
    - Ensures DOT numbers are stored as strings.
    - Expands 'carrier_operation' codes into readable labels.
    - Normalizes year-like columns so they display cleanly as year strings.
    - Maps the ML model score ('ml_score') into 'company_fit_score' and sorts by that score.
    - Reorders columns so key identification/contact fields appear first.
    - Merges in any previously saved prospect status information from
      STATUS_PATH, if that file exists.
    """
    df = pd.read_parquet(path)

    # Standardize all column names to lowercase for consistent access
    df.columns = df.columns.str.lower()

    # Ensure DOT numbers are strings to preserve leading zeros and allow safe joins
    if "dot_number" in df.columns:
        df["dot_number"] = df["dot_number"].astype(str)

    # Normalize DQS (data quality score) if present
    # Stored as a numeric column in [0, 1] with non-numeric values coerced to NaN
    if "dqs" in df.columns:
        df["dqs"] = pd.to_numeric(df["dqs"], errors="coerce")

    # Map 'carrier_operation' codes to descriptive text where available
    if "carrier_operation" in df.columns:
        df["carrier_operation"] = (
            df["carrier_operation"]
            .map(
                {
                    "A": "Interstate",
                    "B": "Intrastate Hazmat",
                    "C": "Intrastate Non-Hazmat",
                }
            )
            .fillna(df["carrier_operation"])
        )

    # Normalize mileage year fields so they display as year-like strings
    for col in ["mcs150_mileage_year", "recent_mileage_year"]:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce").astype("Int64").astype(str)
            )

    # Map ML model score to 'company_fit_score' used throughout the app
    if "ml_score" in df.columns:
        df["company_fit_score"] = pd.to_numeric(df["ml_score"], errors="coerce")
    else:
        # Fallback: if ml_score is missing, keep the column so downstream code doesn't break
        df["company_fit_score"] = np.nan

    # Move key identification and contact columns to the front
    display_columns = [
        "dot_number",
        "legal_name",
        "company_fit_score",
        "email_address",
        "telephone",
    ]
    rest = [c for c in df.columns if c not in display_columns]
    df = df[display_columns + rest]

    # Sort once by 'company_fit_score' so "top companies" is well defined
    df = df.sort_values("company_fit_score", ascending=False)

    # ----------------------------------------------------------
    # Attach persisted 'prospect_status' from STATUS_PATH (if any)
    # ----------------------------------------------------------
    df["dot_number"] = df["dot_number"].astype(str)

    if os.path.exists(STATUS_PATH):
        try:
            status_df = pd.read_parquet(STATUS_PATH)
            status_df["dot_number"] = status_df["dot_number"].astype(str)

            # Ensure exactly one 'prospect_status' per DOT; latest record wins
            status_df = (
                status_df[["dot_number", "prospect_status"]]
                .dropna(subset=["dot_number"])
                .drop_duplicates(subset=["dot_number"], keep="last")
            )

            # Merge saved statuses into the main DataFrame
            df = df.merge(
                status_df,
                on="dot_number",
                how="left",
                suffixes=("", "_saved"),
            )

            # If merged file provides a saved status, use it; otherwise apply default
            if "prospect_status_saved" in df.columns:
                df["prospect_status"] = df["prospect_status_saved"].fillna(
                    df.get("prospect_status", "Not Contacted")
                )
                df.drop(columns=["prospect_status_saved"], inplace=True)
            else:
                if "prospect_status" not in df.columns:
                    df["prospect_status"] = "Not Contacted"

        except Exception as e:
            # If the status file cannot be read (missing/corrupted), ensure
            # a 'prospect_status' column still exists with a default value
            if "prospect_status" not in df.columns:
                df["prospect_status"] = "Not Contacted"
    else:
        # If there is no status file yet, initialize 'prospect_status' with a default
        if "prospect_status" not in df.columns:
            df["prospect_status"] = "Not Contacted"

    return df


# Main dataset used throughout the app
df = load_data(DATA_PATH)

# ----------------------------------------------------------
# Initialize and apply in-session prospect_status_map
# ----------------------------------------------------------
# This dictionary tracks prospect status changes for the current user
# session, keyed by DOT number. It is updated via the data editor and
# persisted to STATUS_PATH when the user presses "Commit".
if "prospect_status_map" not in st.session_state:
    if "dot_number" in df.columns and "prospect_status" in df.columns:
        st.session_state["prospect_status_map"] = (
            df[["dot_number", "prospect_status"]]
            .dropna(subset=["dot_number"])
            .assign(dot_number=lambda d: d["dot_number"].astype(str))
            .set_index("dot_number")["prospect_status"]
            .to_dict()
        )
    else:
        st.session_state["prospect_status_map"] = {}

status_map = st.session_state["prospect_status_map"]

# Apply the in-session status map to the main DataFrame
if "dot_number" in df.columns:
    df["dot_number"] = df["dot_number"].astype(str)
    df["prospect_status"] = df["dot_number"].map(status_map).fillna("Not Contacted")

# ------------------------------------------------------------
# Prospect status choices used throughout the UI
# ------------------------------------------------------------
PROSPECT_STATUS_OPTIONS = [
    "Not Contacted",
    "Contacted",
    "Follow-Up Scheduled",
    "Have Policy with Us",
    "Not Interested",
    "Bad Fit",
]

# ------------------------------------------------------------------
# GeoJSON loading helpers for county / state maps
# ------------------------------------------------------------------
# @st.cache_data
# def load_zcta_geojson():
#     """
#     Load the nationwide ZCTA GeoJSON from disk.
#
#     This file is expected to contain all ZCTAs.
#     The result is cached so it is only read once per session.
#     """
#     with open("2024_us_zcta.geojson") as f:
#         return json.load(f)


@st.cache_data
def load_county_geojson():
    """
    Load the nationwide county GeoJSON from disk.

    This file is expected to contain all U.S. counties with FIPS codes.
    The result is cached so it is only read once per session.
    """
    with open("tl_2024_us_county.geojson") as f:
        return json.load(f)


@st.cache_data
def state_zctas_geojson(state: str):
    """
    Construct a GeoJSON FeatureCollection containing only the ZCTAs
    belonging to a single state, identified by

    This subset is used to draw the ZCTA-level choropleth when a single
    state is selected in the filters.
    """
    geojson_path = f"data/zctas/zcta_{state}.geojson"
    with open(geojson_path) as f:
        return json.load(f)


@st.cache_data
def load_state_counties_geojson(state_fips: str):
    """
    Construct a GeoJSON FeatureCollection containing only the counties
    belonging to a single state, identified by its 2-digit FIPS code.

    This subset is used to draw the county-level choropleth when a single
    state is selected in the filters.
    """
    full_geojson = load_county_geojson()
    features = [
        feat
        for feat in full_geojson["features"]
        if feat["properties"].get("STATEFP") == state_fips
    ]
    return {"type": "FeatureCollection", "features": features}


@st.cache_data
def get_state_zcta_frame(state_abbr: str) -> pd.DataFrame:
    geojson = state_zctas_geojson(state_abbr.lower())

    records = []
    for feature in geojson["features"]:
        props = feature["properties"]
        records.append(
            {
                "phy_zip": props["GEOID20"],  # adjust if different
                "zcta_label": props.get("NAME", props["GEOID20"]),
            }
        )

    return pd.DataFrame(records)


@st.cache_data
def get_state_county_lookup(state_fips: str) -> pd.DataFrame:
    """
    Build a lookup table of counties for a single state from the county
    GeoJSON.

    Returns:
        DataFrame with one row per county, containing:
        - county_fips: combined state + county FIPS code (GEOID)
        - county_name: human-readable county name
    """
    full_geojson = load_county_geojson()
    rows = []
    for feat in full_geojson["features"]:
        props = feat.get("properties", {})
        if props.get("STATEFP") == state_fips:
            rows.append(
                {
                    "county_fips": props.get("GEOID"),
                    "county_name": props.get("NAME"),
                }
            )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# Numeric helper functions
# ------------------------------------------------------------------
@st.cache_data
def get_numeric_series(df_in: pd.DataFrame, col: str) -> pd.Series | None:
    """
    Convert a column to a numeric Series with non-parsable entries coerced
    to NaN. The result is cached for each (DataFrame, column) pair to
    avoid repeated work.

    Returns:
        A numeric Series aligned to df_in.index if the column exists,
        otherwise None.
    """
    if col not in df_in.columns:
        return None
    return pd.to_numeric(df_in[col], errors="coerce")


@st.cache_data
def compute_numeric_metadata(df_in: pd.DataFrame) -> dict:
    """
    Pre-compute basic numeric metadata (min, max, 99th percentile) for
    the main numeric columns used in slider controls and default ranges.

    This function runs once per session for the loaded DataFrame and the
    returned dictionary is reused to configure UI controls.

    Returns:
        A dictionary where keys are column names and values are dictionaries
        with 'min', 'max', and 'q99' entries for each numeric column.
    """
    cols_of_interest = [
        "recent_mileage",
        "driver_total",
        "nbr_power_unit",
        "num_filings",
        "num_unique_companies",
        "median_gap_days",
        "total_crashes",
        "total_at_fault_crashes",
        "pct_at_fault",
        "safety_index",
    ]
    meta: dict[str, dict[str, float]] = {}

    for col in cols_of_interest:
        if col not in df_in.columns:
            continue
        s = pd.to_numeric(df_in[col], errors="coerce")
        s = s[s.notna()]
        if s.empty:
            continue
        meta[col] = {
            "min": float(s.min()),
            "max": float(s.max()),
            "q99": float(s.quantile(0.99)),
        }
    return meta


numeric_meta = compute_numeric_metadata(df)


def apply_range_filter_with_optional_na(
    mask: pd.Series,
    df_in: pd.DataFrame,
    col: str,
    low,
    high,
) -> pd.Series:
    """
    Apply a numeric range filter for a single column and combine the result
    with the existing boolean 'mask'.

    Rows where the column is missing (NaN) are kept. This is used in
    filters where missing values should not automatically exclude a row
    (for example, in some insurance-related filters).

    Args:
        mask: Existing boolean Series specifying which rows are currently kept.
        df_in: DataFrame containing the column to filter.
        col: Name of the numeric column to filter on.
        low: Lower bound (inclusive).
        high: Upper bound (inclusive).

    Returns:
        Updated boolean mask Series.
    """
    s_all = get_numeric_series(df_in, col)
    if s_all is None:
        return mask

    has_val = s_all.notna()
    in_range = (s_all >= low) & (s_all <= high)
    return mask & ((~has_val) | in_range)


# ------------------------------------------------------------------
# Constants / mappings used by multiple sections
# ------------------------------------------------------------------
fit_min = (
    float(df["company_fit_score"].min()) if "company_fit_score" in df.columns else 0.0
)
fit_max = (
    float(df["company_fit_score"].max()) if "company_fit_score" in df.columns else 1.0
)

# Default minimum fit score used in the CSV filename when filters are not active
min_fit = 0.0

# Mapping from human-readable operation type labels to underlying flag columns
flag_label_to_col = {
    "Private Carrier": "private_only",
    "Authorized for Hire": "authorized_for_hire",
    "Exempt for Hire": "exempt_for_hire",
    "Private Property": "private_property",
    "Private Passenger Business": "private_passenger_business",
    "Private Passenger Non-Business": "private_passenger_nonbusiness",
    "Migrant": "migrant",
    "Federal Government": "federal_government",
    "State Government": "state_government",
    "Local Government": "local_government",
    "Indian Tribe": "indian_tribe",
}

# Mapping from state postal abbreviations to 2-digit FIPS codes for county maps
STATE_ABBR_TO_FIPS = {
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "DC": "11",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
}

# Column names reused in several sections to avoid hard-coding
mileage_col = "recent_mileage"
drivers_col = "driver_total"
units_col = "nbr_power_unit"
filings_col = "num_filings"
insurers_col = "num_unique_companies"
median_gap_col = "median_gap_days"
total_crashes_col = "total_crashes"
at_fault_crashes_col = "total_at_fault_crashes"
pct_at_fault_col = "pct_at_fault"
safety_index_col = "safety_index"

# ------------------------------------------------------------------
# Sidebar filters
# ------------------------------------------------------------------
if "phy_state" in df.columns:
    st.sidebar.header("Filter")

    # Set of codes that represent non-US states or provinces to be excluded
    # from the main state filter control
    exclude_states = {
        "AB",
        "AG",
        "AS",
        "BC",
        "BN",
        "BS",
        "BZ",
        "CH",
        "CI",
        "CL",
        "CP",
        "CR",
        "CS",
        "DF",
        "DG",
        "DO",
        "FJ",
        "GB",
        "GE",
        "GJ",
        "GT",
        "GU",
        "HD",
        "HN",
        "JA",
        "KW",
        "MB",
        "MC",
        "MP",
        "MR",
        "MX",
        "NB",
        "NL",
        "NS",
        "NT",
        "ON",
        "PE",
        "PR",
        "PU",
        "QC",
        "QE",
        "QI",
        "RO",
        "SI",
        "SK",
        "SL",
        "SO",
        "SV",
        "TA",
        "TB",
        "TL",
        "VC",
        "VI",
        "YT",
        "ZA",
    }

    # States that are generally considered west of the Mississippi River
    # (used for a convenience filter in the UI)
    west_states = {
        "WA",
        "OR",
        "CA",
        "NV",
        "ID",
        "ND",
        "MT",
        "SD",
        "MN",
        "IA",
        "MO",
        "KS",
        "NE",
        "OK",
        "TX",
        "AZ",
        "NM",
        "CO",
        "UT",
        "LA",
        "AR",
        "WY",
        "AK",
        "HI",
    }

    all_states = sorted(df["phy_state"].dropna().unique())
    states = [s for s in all_states if s not in exclude_states]

    # ------------------------------------------------------------------
    # Precompute ranges for fleet size sliders using numeric_meta
    # ------------------------------------------------------------------
    def get_meta(col, key, default=0):
        """
        Safely retrieve a specific statistic (e.g., min, max, q99) for a
        given numeric column from the 'numeric_meta' dictionary.

        If the column or key is not present, return the provided default.
        """
        if col in numeric_meta and key in numeric_meta[col]:
            return numeric_meta[col][key]
        return default

    # Recent mileage (used in fleet size filters and outlier capping)
    miles_min = int(get_meta(mileage_col, "min", 0))
    miles_max = int(get_meta(mileage_col, "max", 0))
    miles_outlier_cap = get_meta(mileage_col, "q99", None)

    # Driver counts
    drivers_min = int(get_meta(drivers_col, "min", 0))
    drivers_max = int(get_meta(drivers_col, "max", 0))
    drivers_outlier_cap = get_meta(drivers_col, "q99", None)

    # Power unit counts
    units_min = int(get_meta(units_col, "min", 0))
    units_max = int(get_meta(units_col, "max", 0))
    units_outlier_cap = get_meta(units_col, "q99", None)

    # Slider maximums are capped at the 99th percentile where available
    miles_ui_max = (
        miles_max
        if miles_outlier_cap is None
        else min(miles_max, int(miles_outlier_cap))
    )
    drivers_ui_max = (
        drivers_max
        if drivers_outlier_cap is None
        else min(drivers_max, int(drivers_outlier_cap))
    )
    units_ui_max = (
        units_max
        if units_outlier_cap is None
        else min(units_max, int(units_outlier_cap))
    )

    # ------------------------------------------------------------------
    # Precompute ranges for insurance / accident columns
    # ------------------------------------------------------------------
    filings_min = (
        int(get_meta(filings_col, "min", 0)) if filings_col in numeric_meta else None
    )
    filings_max = (
        int(get_meta(filings_col, "max", 0)) if filings_col in numeric_meta else None
    )

    insurers_min = (
        int(get_meta(insurers_col, "min", 0)) if insurers_col in numeric_meta else None
    )
    insurers_max = (
        int(get_meta(insurers_col, "max", 0)) if insurers_col in numeric_meta else None
    )

    gap_min = (
        int(get_meta(median_gap_col, "min", 0))
        if median_gap_col in numeric_meta
        else None
    )
    gap_max = (
        int(get_meta(median_gap_col, "max", 0))
        if median_gap_col in numeric_meta
        else None
    )

    total_crashes_max = (
        int(get_meta(total_crashes_col, "max", 0))
        if total_crashes_col in numeric_meta
        else None
    )
    at_fault_crashes_max = (
        int(get_meta(at_fault_crashes_col, "max", 0))
        if at_fault_crashes_col in numeric_meta
        else None
    )
    pct_at_fault_max = (
        float(get_meta(pct_at_fault_col, "max", 0.0))
        if pct_at_fault_col in numeric_meta
        else None
    )

    safety_index_min = (
        float(get_meta(safety_index_col, "min", 0.0))
        if safety_index_col in numeric_meta
        else None
    )
    safety_index_max = (
        float(get_meta(safety_index_col, "max", 0.0))
        if safety_index_col in numeric_meta
        else None
    )

    # ------------------------------------------------------------------
    # Defaults for basic filters (country, mail, hazmat, territories)
    # ------------------------------------------------------------------
    countries = (
        sorted(df["phy_country"].dropna().unique())
        if "phy_country" in df.columns
        else []
    )
    default_country = (
        "US" if "US" in countries else (countries[0] if countries else None)
    )

    mail_options = (
        sorted(df["us_mail"].dropna().unique()) if "us_mail" in df.columns else []
    )
    hm_options = (
        sorted(df["hm_flag"].dropna().unique()) if "hm_flag" in df.columns else []
    )

    default_mail = (
        "N" if "N" in mail_options else (mail_options[0] if mail_options else None)
    )
    default_hm = "N" if "N" in hm_options else (hm_options[0] if hm_options else None)

    # Initialize session_state defaults that must persist across reruns
    if "exclude_territories" not in st.session_state:
        st.session_state["exclude_territories"] = True

    for key in ["cap_mileage_outliers", "cap_driver_outliers", "cap_unit_outliers"]:
        if key not in st.session_state:
            st.session_state[key] = True

    if "phy_country" in df.columns and "phy_country_selection" not in st.session_state:
        if default_country:
            st.session_state["phy_country_selection"] = [default_country]

    if "us_mail" in df.columns:
        valid_mail_values = ["All"] + mail_options
        if (
            "us_mail_filter" not in st.session_state
            or st.session_state["us_mail_filter"] not in valid_mail_values
        ):
            st.session_state["us_mail_filter"] = default_mail

    if "hm_flag" in df.columns:
        valid_hm_values = ["All"] + hm_options
        if (
            "hm_flag_filter" not in st.session_state
            or st.session_state["hm_flag_filter"] not in valid_hm_values
        ):
            st.session_state["hm_flag_filter"] = default_hm

    if "ready_to_contact" not in st.session_state:
        st.session_state["ready_to_contact"] = False

    # ------------------------------------------------------------------
    # Reset button: restore all filters to consistent default values
    # ------------------------------------------------------------------
    def reset_all_filters():
        ss = st.session_state

        # Company fit score filter
        ss["min_fit_score"] = 0.0

        # Data quality score (DQS) filter
        ss["min_dqs"] = 0.4

        # Geographic filters
        ss["phy_state_selection"] = []
        ss["west_of_mississippi"] = False
        ss["exclude_ak_hi_ny_nj"] = False
        ss["verified_addresses_only"] = False
        ss["county_filter"] = []

        # Fleet size filters
        if mileage_col in df.columns:
            ss["mileage_min"] = miles_min
            ss["mileage_max"] = miles_ui_max

        if drivers_col in df.columns:
            ss["min_drivers"] = max(1, drivers_min)
            ss["max_drivers"] = drivers_ui_max

        if units_col in df.columns:
            ss["min_units"] = max(1, units_min)
            ss["max_units"] = units_ui_max

        # Default filters for country, mail, and hazmat flags
        if default_country is not None:
            ss["phy_country_selection"] = [default_country]

        if default_mail is not None:
            ss["us_mail_filter"] = default_mail

        if default_hm is not None:
            ss["hm_flag_filter"] = default_hm

        ss["exclude_territories"] = True

        # Outlier capping flags
        ss["cap_mileage_outliers"] = True
        ss["cap_driver_outliers"] = True
        ss["cap_unit_outliers"] = True

        # Operation type filters (including cargo filter)
        ss["operation_flags"] = []
        ss["carrier_type_filter"] = []
        ss["cargo_categorized_include"] = []
        ss["cargo_categorized_exclude"] = []

        # Insurance filters
        ss["has_insurance_info"] = False
        if filings_min is not None and filings_max is not None:
            ss["filings_range"] = (filings_min, filings_max)
        if insurers_min is not None and insurers_max is not None:
            ss["insurers_range"] = (insurers_min, insurers_max)
        if gap_min is not None and gap_max is not None:
            ss["median_gap_min"] = gap_min
            ss["median_gap_max"] = gap_max

        # Accident filters
        ss["has_accident_info"] = False
        if total_crashes_max is not None:
            ss["max_total_crashes"] = total_crashes_max
        if at_fault_crashes_max is not None:
            ss["max_total_at_fault"] = at_fault_crashes_max
        if pct_at_fault_max is not None:
            ss["max_pct_at_fault"] = pct_at_fault_max * 100.0
        if safety_index_min is not None:
            ss["min_safety_index"] = safety_index_min

        # Prospect contactability filter
        ss["ready_to_contact"] = False

        # Clear search fields used in the company list section
        ss["dot_search"] = ""
        ss["name_search"] = ""

    st.sidebar.button("Reset filters", on_click=reset_all_filters)

    # ------------------------------------------------------------------
    # Company fit score filter (applies to the entire dataset)
    # ------------------------------------------------------------------
    min_fit = st.sidebar.slider(
        "Minimum Company Fit Score",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        key="min_fit_score",
        help="Use this to focus on higher-ranked prospects.",
    )

    # Start with a mask that keeps all rows; each filter refines this mask
    mask = pd.Series(True, index=df.index)

    # Filter by company fit score
    if "company_fit_score" in df.columns:
        mask &= df["company_fit_score"] >= float(min_fit)

    # ------------------------------------------------------------------
    # Geographic filters
    # ------------------------------------------------------------------
    with st.sidebar.expander("Geographic Filters", expanded=False):
        verified_only = st.checkbox(
            "Only include verified addresses",
            value=False,
            key="verified_addresses_only",
            help="Includes only companies where the address has been successfully geocoded.",
        )

        west_only = st.checkbox(
            "West of the Mississippi",
            value=False,
            key="west_of_mississippi",
            help="Filter to states west of the Mississippi River.",
        )

        exclude_special = st.checkbox(
            "Exclude AK, HI, NJ, NY",
            value=False,
            key="exclude_ak_hi_ny_nj",
        )

        selected_states = st.multiselect(
            "Physical State",
            options=states,
            key="phy_state_selection",
            help="Select one or multiple states. Selecting one state will show a county breakdown.",
        )

        selected_zips: list[str] = []
        if selected_states and len(selected_states) == 1 and "phy_zip" in df.columns:
            state_for_zips = selected_states[0]
            available_zips = (
                df.loc[df["phy_state"] == state_for_zips, "phy_zip"]
                .dropna()
                .sort_values()
                .unique()
                .tolist()
            )

            selected_zips = st.multiselect(
                f"ZCTA (only for {state_for_zips})",
                options=available_zips,
                key="zcta_filter",
            )

    # Build human-readable summary of geographic filters and update mask
    state_msg_parts: list[str] = []

    if west_only:
        mask &= df["phy_state"].isin(west_states)
        state_msg_parts.append("West of the Mississippi only")

    if selected_states:
        mask &= df["phy_state"].isin(selected_states)

        if len(selected_states) == 1 and selected_zips and "phy_zip" in df.columns:
            mask &= df["phy_zip"].isin(selected_zips)
            state_msg_parts.append(f"{selected_states[0]} ({', '.join(selected_zips)})")
        else:
            state_msg_parts.append(", ".join(selected_states))
    else:
        state_msg_parts.append("all states")

    if exclude_special:
        special_exclude = {"AK", "HI", "NJ", "NY"}
        mask &= ~df["phy_state"].isin(special_exclude)
        state_msg_parts.append("excluded AK, HI, NJ, NY")

    if verified_only and "match_status" in df.columns:
        mask &= df["match_status"] == "Match"
        state_msg_parts.append("verified addresses only")

    geo_summary = "; ".join(state_msg_parts)

    # ------------------------------------------------------------------
    # Fleet size filters (power units, drivers, mileage)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Fleet Size Filters", expanded=False):
        # Power units filter
        if units_col in df.columns:
            # Initialize defaults once, if they aren't set yet
            if "min_units" not in st.session_state:
                st.session_state["min_units"] = max(1, units_min)
            if "max_units" not in st.session_state:
                st.session_state["max_units"] = units_ui_max

            min_units_val = st.number_input(
                "Min power units",
                min_value=units_min,
                max_value=units_max,
                step=1,
                key="min_units",
                help="Minimum number of power units operated by the carrier.",
            )
            max_units_val = st.number_input(
                "Max power units",
                min_value=units_min,
                max_value=units_max,
                step=1,
                key="max_units",
                help=(
                    "Maximum number (outliers excluded) of power units operated by the carrier. "
                    f"True maximum in dataset: {units_max:,}."
                ),
            )

            # Use the values as entered. If the minimum is greater than the
            # maximum, no rows should pass this filter.
            u_low = min_units_val
            u_high = max_units_val

            s_all = get_numeric_series(df, units_col)
            if s_all is not None:
                if u_low <= u_high:
                    mask &= s_all.between(u_low, u_high)
                else:
                    # Invalid range (min > max) → no rows match.
                    mask &= False

        # Driver count filter
        if drivers_col in df.columns:
            min_drivers_val = st.number_input(
                "Min drivers",
                min_value=drivers_min,
                max_value=drivers_max,
                value=st.session_state.get("min_drivers", max(1, drivers_min)),
                step=1,
                key="min_drivers",
                help="Minimum number of drivers employed by the carrier.",
            )
            max_drivers_val = st.number_input(
                "Max drivers",
                min_value=drivers_min,
                max_value=drivers_max,
                value=st.session_state.get("max_drivers", drivers_ui_max),
                step=1,
                key="max_drivers",
                help=(
                    "Maximum number (outliers excluded) of drivers employed by the carrier. "
                    f"True maximum in dataset: {drivers_max:,}."
                ),
            )

            # Use the values as entered; if min > max, treat as an empty range.
            d_low = min_drivers_val
            d_high = max_drivers_val

            s_all = get_numeric_series(df, drivers_col)
            if s_all is not None:
                if d_low <= d_high:
                    mask &= s_all.between(d_low, d_high)
                else:
                    mask &= False

        # Recent mileage filter
        if mileage_col in df.columns:
            min_miles_input = st.number_input(
                "Min recent mileage",
                min_value=miles_min,
                max_value=miles_max,
                value=st.session_state.get("mileage_min", miles_min),
                step=1000,
                key="mileage_min",
                help="Lower bound for the carrier's most recently reported mileage.",
            )

            max_miles_input = st.number_input(
                "Max recent mileage",
                min_value=miles_min,
                max_value=miles_max,
                value=st.session_state.get("mileage_max", miles_ui_max),
                step=1000,
                key="mileage_max",
                help=(
                    "Upper bound (outliers excluded) for the carrier's most recently reported mileage. "
                    f"True maximum in dataset: {miles_max:,}."
                ),
            )

            # Use the values as entered; if min > max, no rows should match.
            low = min_miles_input
            high = max_miles_input

            s_all = get_numeric_series(df, mileage_col)
            if s_all is not None:
                if low <= high:
                    mask &= s_all.between(low, high)
                else:
                    mask &= False

    # ------------------------------------------------------------------
    # Operation-type filters (flag columns + carrier_operation)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Operation Type Filters", expanded=False):
        # Identify which operation flags actually exist in the dataset
        available_labels = [
            label for label, col in flag_label_to_col.items() if col in df.columns
        ]

        # Filter companies where any selected operation flags are true
        selected_flag_labels = st.multiselect(
            "Include companies where ANY of these flags are true:",
            options=available_labels,
            key="operation_flags",
            help="Use to focus on specific operation types (e.g., private carrier, authorized for hire). A row is kept if ANY selected flag is true.",
        )

        if selected_flag_labels:
            selected_cols = [flag_label_to_col[label] for label in selected_flag_labels]
            any_flag_true = pd.Series(False, index=df.index)
            for col in selected_cols:
                if col not in df.columns:
                    continue
                s = df[col]
                col_true = (s == "Y") | (s == 1) | (s == True)
                any_flag_true |= col_true
            mask &= any_flag_true

        # Optional filter for 'carrier_operation' values
        if "carrier_operation" in df.columns:
            carrier_types = sorted(df["carrier_operation"].dropna().unique())
            selected_carrier_types = st.multiselect(
                "Carrier Type",
                options=carrier_types,
                key="carrier_type_filter",
                help="Filter by FMCSA carrier_operation type.",
            )
            if selected_carrier_types:
                mask &= df["carrier_operation"].isin(selected_carrier_types)

        # Cargo Carried filters using pipe "|" separator
        if "cargo_categorized" in df.columns:

            # Predetermined FMCSA-style categories
            ALL_CARGO_CATEGORIES = [
                "General Freight",
                "Household Goods",
                "Metal: sheets, coils, rolls",
                "Motor Vehicles",
                "Drive/Tow away",
                "Logs, Poles, Beams, Lumber",
                "Building Materials",
                "Mobile Homes",
                "Machinery, Large Objects",
                "Fresh Produce",
                "Liquids/Gases",
                "Intermodal Cont.",
                "Passengers",
                "Oilfield Equipment",
                "Livestock",
                "Grain, Feed, Hay",
                "Coal/Coke",
                "Meat",
                "Garbage/Refuse",
                "US Mail",
                "Chemicals",
                "Commodities Dry Bulk",
                "Refrigerated Food",
                "Beverages",
                "Paper Products",
                "Utilities",
                "Agricultural/Farm Supplies",
                "Construction",
                "Water Well",
                "Landscaping/Lawn Care",
                "Dry Foods (Non-Refrigerated)",
                "Roads/Paving",
                "Recyclables",
                "Medical",
                "Other",
                "Null",
            ]

            cargo_series = df["cargo_categorized"].dropna().astype(str)

            # Detect which categories actually appear in the DF using exact membership
            present_categories = set()
            for entry in cargo_series:
                parts = [p.strip() for p in entry.split("|") if p.strip()]
                for p in parts:
                    if p in ALL_CARGO_CATEGORIES:
                        present_categories.add(p)

            # Sort alphabetically but push Other and Null to the bottom
            def sort_key(cat):
                if cat == "Other":
                    return (1, cat)
                if cat == "Null":
                    return (2, cat)
                return (0, cat.lower())

            cargo_options = sorted(present_categories, key=sort_key)

            # ----------- INCLUDE FILTER (ANY of) -----------
            selected_include = st.multiselect(
                "Cargo Carried (ANY of – INCLUDE)",
                options=cargo_options,
                key="cargo_categorized_include",
                help="Keep companies carrying ANY of these categories.",
            )

            # ----------- EXCLUDE FILTER (NONE of) -----------
            selected_exclude = st.multiselect(
                "Cargo Carried (NONE of – EXCLUDE)",
                options=cargo_options,
                key="cargo_categorized_exclude",
                help="Exclude companies carrying ANY of these categories.",
            )

            # FAST lookup sets
            include_set = set(selected_include)
            exclude_set = set(selected_exclude)

            def parse_categories(val):
                if pd.isna(val):
                    return set()
                return {p.strip() for p in str(val).split("|") if p.strip()}

            # Apply INCLUDE (must contain at least one)
            if include_set:
                mask &= df["cargo_categorized"].apply(
                    lambda v: len(parse_categories(v) & include_set) > 0
                )

            # Apply EXCLUDE (must contain none)
            if exclude_set:
                mask &= df["cargo_categorized"].apply(
                    lambda v: len(parse_categories(v) & exclude_set) == 0
                )

    # ------------------------------------------------------------------
    # Prospective Clients filters (moved here)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Prospective Clients Filters", expanded=False):
        # Require at least one contact method (email or phone)
        ready_only = st.checkbox(
            "Only show companies that have email or phone",
            key="ready_to_contact",
            help="Keep only carriers that have at least one contact method (email or phone).",
        )

        # Prospect status filter behaves like the state filter:
        # if no status is selected, no filtering is applied.
        if "prospect_status" in df.columns:
            selected_statuses = st.multiselect(
                "Prospect Status",
                options=PROSPECT_STATUS_OPTIONS,
                default=[],
                key="prospect_status_filter",
                help="Filter companies by your progress with them.",
            )
        else:
            selected_statuses = []

    # Apply contactability filter if enabled
    if ready_only:
        email_exists = (
            (
                df["email_address"].notna()
                & (df["email_address"].astype(str).str.strip() != "")
            )
            if "email_address" in df.columns
            else pd.Series(False, index=df.index)
        )

        phone_exists = (
            (df["telephone"].notna() & (df["telephone"].astype(str).str.strip() != ""))
            if "telephone" in df.columns
            else pd.Series(False, index=df.index)
        )

        mask &= email_exists | phone_exists

    # Apply prospect status filter only if at least one status was selected
    if "prospect_status" in df.columns and selected_statuses:
        mask &= df["prospect_status"].isin(selected_statuses)

    # ------------------------------------------------------------------
    # Insurance history filters
    # ------------------------------------------------------------------
    with st.sidebar.expander("Insurance History Filters", expanded=False):
        has_insurance = st.checkbox(
            "Only show companies with insurance history",
            value=False,
            key="has_insurance_info",
            help="Keep only companies with at least one insurance filing on record.",
        )

        # Filter by total number of insurance filings
        if filings_min is not None and filings_max is not None:
            default_filings_range = st.session_state.get(
                "filings_range", (filings_min, filings_max)
            )
            min_filings, max_filings = st.slider(
                "Total Insurance Filings",
                min_value=filings_min,
                max_value=filings_max,
                value=default_filings_range,
                step=1,
                key="filings_range",
                help="Range of total insurance filings per company.",
            )

            mask = apply_range_filter_with_optional_na(
                mask,
                df,
                filings_col,
                min_filings,
                max_filings,
            )

        # Filter by number of distinct insurance companies used
        if insurers_min is not None and insurers_max is not None:
            default_insurers_range = st.session_state.get(
                "insurers_range", (insurers_min, insurers_max)
            )
            min_insurers, max_insurers = st.slider(
                "Insurance Companies Used",
                min_value=insurers_min,
                max_value=insurers_max,
                value=default_insurers_range,
                step=1,
                key="insurers_range",
                help="Range of distinct insurers that each company has used.",
            )

            mask = apply_range_filter_with_optional_na(
                mask,
                df,
                insurers_col,
                min_insurers,
                max_insurers,
            )

        # Filter by median days between insurance filings
        if gap_min is not None and gap_max is not None:
            min_gap = st.number_input(
                "Min median days between filings",
                value=st.session_state.get("median_gap_min", gap_min),
                step=1,
                key="median_gap_min",
                help="Lower bound on the median days between successive insurance filings.",
            )
            max_gap = st.number_input(
                "Max median days between filings",
                value=st.session_state.get("median_gap_max", gap_max),
                step=1,
                key="median_gap_max",
                help="Upper bound on the median days between successive insurance filings.",
            )

            low_gap = min(min_gap, max_gap)
            high_gap = max(min_gap, max_gap)

            mask = apply_range_filter_with_optional_na(
                mask,
                df,
                median_gap_col,
                low_gap,
                high_gap,
            )

        # Optionally require at least one insurance filing (non-missing)
        if has_insurance and filings_col in df.columns:
            s_all = get_numeric_series(df, filings_col)
            if s_all is not None:
                mask &= s_all.notna()

    # ------------------------------------------------------------------
    # Accident history filters
    # ------------------------------------------------------------------
    with st.sidebar.expander("Accident History Filters", expanded=False):
        has_accidents = st.checkbox(
            "Only include companies with accident history",
            value=False,
            key="has_accident_info",
            help="Keep only companies with at least one recorded crash.",
        )

        # Upper bound on total crashes
        if (
            total_crashes_col in df.columns
            and total_crashes_max is not None
            and total_crashes_max > 0
        ):
            max_total_crashes = st.slider(
                "Max total crashes",
                min_value=0,
                max_value=total_crashes_max,
                value=st.session_state.get("max_total_crashes", total_crashes_max),
                step=1,
                key="max_total_crashes",
                help="Upper bound on the total number of crashes linked to the company based on FARS/CRSS reports.",
            )

            s_all = get_numeric_series(df, total_crashes_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all <= max_total_crashes)

        # Upper bound on at-fault crashes
        if (
            at_fault_crashes_col in df.columns
            and at_fault_crashes_max is not None
            and at_fault_crashes_max > 0
        ):
            max_total_at_fault = st.slider(
                "Max at-fault crashes",
                min_value=0,
                max_value=at_fault_crashes_max,
                value=st.session_state.get("max_total_at_fault", at_fault_crashes_max),
                step=1,
                key="max_total_at_fault",
                help="Upper bound on the total number of at-fault crashes.",
            )

            s_all = get_numeric_series(df, at_fault_crashes_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all <= max_total_at_fault)

        # Upper bound on percent of crashes where the company was at fault
        if (
            pct_at_fault_col in df.columns
            and pct_at_fault_max is not None
            and pct_at_fault_max > 0
        ):
            display_max_pct = st.slider(
                "Max % at fault",
                min_value=0.0,
                max_value=float(pct_at_fault_max * 100.0),
                value=float(
                    st.session_state.get(
                        "max_pct_at_fault",
                        pct_at_fault_max * 100.0,
                    )
                ),
                step=1.0,
                key="max_pct_at_fault",
                help="Upper bound on the percent of crashes where the company was likely at fault.",
            )

            max_pct_at_fault = display_max_pct / 100.0

            s_all = get_numeric_series(df, pct_at_fault_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all <= max_pct_at_fault)

        # Minimum safety index (higher values indicate better safety performance)
        if (
            safety_index_col in df.columns
            and safety_index_min is not None
            and safety_index_max is not None
        ):
            min_safety_idx = st.slider(
                "Min safety index",
                min_value=float(safety_index_min),
                max_value=float(safety_index_max),
                value=float(st.session_state.get("min_safety_index", safety_index_min)),
                step=0.01,
                key="min_safety_index",
                help="Higher Safety Index values indicate better safety performance (fewer accidents per unit of exposure).",
            )

            s_all = get_numeric_series(df, safety_index_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all >= min_safety_idx)

        # Optionally require at least one non-zero crash record
        if has_accidents and total_crashes_col in df.columns:
            s_all = get_numeric_series(df, total_crashes_col)
            if s_all is not None:
                mask &= s_all.notna() & (s_all != 0)

    # ------------------------------------------------------------------
    # Default filters (country, mail, hazmat, territories, outlier caps)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Default Filters", expanded=False):
        territories_to_exclude = {"PR", "GU", "AS", "MP", "VI"}

        # -----------------------------
        # Data Quality Score (DQS) filter
        # -----------------------------
        if "dqs" in df.columns:
            min_dqs = st.slider(
                "Minimum Data Quality Score (DQS)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("min_dqs", 0.4)),
                step=0.01,
                key="min_dqs",
                help=(
                    "DQS is a data quality score based on the completeness "
                    "(lack of NULL values), validity (how accurate the data "
                    "appears to be), and freshness (how recently it has been "
                    "updated)."
                ),
            )

            s_dqs = get_numeric_series(df, "dqs")
            if s_dqs is not None:
                mask &= s_dqs >= float(min_dqs)

        exclude_territories = st.checkbox(
            "Exclude US territories (PR, GU, AS, MP, VI)",
            key="exclude_territories",
            help="Filters out US territories so the dataset is limited to the 50 states (plus DC).",
        )

        if exclude_territories and "phy_state" in df.columns:
            mask &= ~df["phy_state"].isin(territories_to_exclude)

        if "phy_country" in df.columns and default_country is not None:
            selected_countries = st.multiselect(
                "Country",
                options=countries,
                key="phy_country_selection",
                help="Keep only US-based companies.",
            )
            if selected_countries:
                mask &= df["phy_country"].isin(selected_countries)

        if "us_mail" in df.columns and default_mail is not None:
            mail_choice = st.selectbox(
                "US Mail",
                options=["All"] + mail_options,
                key="us_mail_filter",
                help="Filter on whether the company delivers mail as part of its business.",
            )
            if mail_choice != "All":
                mask &= df["us_mail"] == mail_choice

        if "hm_flag" in df.columns and default_hm is not None:
            hm_choice = st.selectbox(
                "Hazardous Material",
                options=["All"] + hm_options,
                key="hm_flag_filter",
                help="Filter companies based on whether they haul hazardous materials.",
            )
            if hm_choice == "N":
                mask &= df["hm_flag"] == "N"
            elif hm_choice == "Y":
                mask &= df["hm_flag"] == "Y"

        # Optional outlier caps based on 99th percentile values
        if units_outlier_cap is not None and units_col in df.columns:
            cap_units = st.checkbox(
                "Exclude extreme power unit outliers (top 1%)",
                key="cap_unit_outliers",
                help="Drop the largest fleets by power units (top 1%) to avoid extreme outliers.",
            )
            if cap_units:
                s_all = get_numeric_series(df, units_col)
                if s_all is not None:
                    mask &= s_all.isna() | (s_all <= units_outlier_cap)

        if drivers_outlier_cap is not None and drivers_col in df.columns:
            cap_drivers = st.checkbox(
                "Exclude extreme driver count outliers (top 1%)",
                key="cap_driver_outliers",
                help="Drop the largest fleets by driver count (top 1%) to focus on more typical companies.",
            )
            if cap_drivers:
                s_all = get_numeric_series(df, drivers_col)
                if s_all is not None:
                    mask &= s_all.isna() | (s_all <= drivers_outlier_cap)

        if miles_outlier_cap is not None and mileage_col in df.columns:
            cap_miles = st.checkbox(
                "Exclude extreme mileage outliers (top 1%)",
                key="cap_mileage_outliers",
                help="Drop the highest 1% of recent mileage values to avoid extreme outliers distorting the view.",
            )
            if cap_miles:
                s_all = get_numeric_series(df, mileage_col)
                if s_all is not None:
                    mask &= s_all.isna() | (s_all <= miles_outlier_cap)

    # ------------------------------------------------------------------
    # Apply the combined mask once to create filtered_df
    # ------------------------------------------------------------------
    filtered_df = df[mask].copy()
else:
    # If the dataset does not contain 'phy_state', use the full DataFrame
    filtered_df = df.copy()

# ----------------------------------------------------------------------
# KPI strip (high-level metrics for current filtered set)
# ----------------------------------------------------------------------
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric("Companies (filtered)", f"{len(filtered_df):,}")

with kpi2:
    if "recent_mileage" in filtered_df.columns:
        s_miles = pd.to_numeric(filtered_df["recent_mileage"], errors="coerce")
        s_miles = s_miles[(s_miles.notna()) & (s_miles != 0)]
        if len(s_miles) > 0:
            median_miles = int(s_miles.median())
            st.metric("Median Miles (non-zero)", f"{median_miles:,}")
        else:
            st.caption("No non-zero mileage values in current filters.")

with kpi3:
    if "num_filings" in df.columns and len(filtered_df) > 0:
        s_ins = get_numeric_series(df, "num_filings")
        if s_ins is not None:
            s_ins_filtered = s_ins.loc[filtered_df.index]
            pct_ins = s_ins_filtered.notna().mean() * 100
            st.metric("% with Insurance History", f"{pct_ins:.1f}%")

with kpi4:
    if "match_status" in filtered_df.columns and len(filtered_df) > 0:
        pct_verified = (filtered_df["match_status"] == "Match").mean() * 100
        st.metric("% Verified Addresses", f"{pct_verified:.1f}%")

# ----------------------------------------------------------------------
# Concise active filter summary (key filters)
# ----------------------------------------------------------------------
active_filters = [
    f"Min fit score ≥ {min_fit:.2f}",
    f"Companies after filters: {len(filtered_df):,}",
]

if "phy_state" in filtered_df.columns:
    selected_states_summary = st.session_state.get("phy_state_selection", [])
    if selected_states_summary:
        active_filters.append("States: " + ", ".join(selected_states_summary))
    else:
        active_filters.append("States: all")

st.caption(" | ".join(active_filters))

# ----------------------------------------------------------------------
# Choropleth + metric-selectable Top 10 bar chart
# ----------------------------------------------------------------------
if "phy_state" in df.columns:
    col_map, col_map_right = st.columns([1, 1])

    # The mapping and bar chart are based on the currently filtered dataset
    source_for_map = filtered_df

    # Aggregations at the state level
    agg_dict = {"CompanyCount": ("phy_state", "size")}
    if "company_fit_score" in source_for_map.columns:
        agg_dict["avg_company_fit_score"] = ("company_fit_score", "mean")
    if "recent_mileage" in source_for_map.columns:
        agg_dict["avg_recent_mileage"] = ("recent_mileage", "mean")
    if "driver_total" in source_for_map.columns:
        agg_dict["avg_drivers"] = ("driver_total", "mean")
    if "nbr_power_unit" in source_for_map.columns:
        agg_dict["avg_power_units"] = ("nbr_power_unit", "mean")
    if "num_filings" in source_for_map.columns:
        agg_dict["InsuranceCount"] = ("num_filings", lambda s: s.notna().sum())
    if "dqs" in source_for_map.columns:
        agg_dict["avg_dqs"] = ("dqs", "mean")

    if len(source_for_map) > 0:
        state_agg = (
            source_for_map.groupby("phy_state")
            .agg(**agg_dict)
            .reset_index()
            .rename(columns={"phy_state": "State"})
        )
    else:
        state_agg = pd.DataFrame(columns=["State", "CompanyCount"])

    # Compute percentage of companies with insurance history per state
    if "CompanyCount" in state_agg.columns and "InsuranceCount" in state_agg.columns:
        state_agg["InsurancePct"] = np.where(
            state_agg["CompanyCount"] > 0,
            state_agg["InsuranceCount"] / state_agg["CompanyCount"] * 100.0,
            np.nan,
        )

    # Compute percentage of companies with verified addresses per state
    if "CompanyCount" in state_agg.columns and "match_status" in source_for_map.columns:
        verified_counts = (
            (source_for_map["match_status"] == "Match")
            .groupby(source_for_map["phy_state"])
            .sum()
            .rename("VerifiedCount")
        )

        state_agg = state_agg.merge(
            verified_counts,
            left_on="State",
            right_index=True,
            how="left",
        )

        state_agg["VerifiedCount"] = state_agg["VerifiedCount"].fillna(0.0)

        state_agg["VerifiedPct"] = np.where(
            state_agg["CompanyCount"] > 0,
            state_agg["VerifiedCount"] / state_agg["CompanyCount"] * 100.0,
            np.nan,
        )

    # Define which metrics the user can visualize on the map/bar chart
    metric_options = {
        "Company Count": ("CompanyCount", "Companies"),
    }

    # Average Company Fit Score
    if "avg_company_fit_score" in state_agg.columns:
        metric_options["Average Company Fit Score"] = (
            "avg_company_fit_score",
            "Average Company Fit Score",
        )

    if "avg_recent_mileage" in state_agg.columns:
        metric_options["Average Recent Mileage"] = (
            "avg_recent_mileage",
            "Average Recent Mileage",
        )
    if "avg_drivers" in state_agg.columns:
        metric_options["Average Drivers"] = (
            "avg_drivers",
            "Average Drivers",
        )
    if "avg_power_units" in state_agg.columns:
        metric_options["Average Power Units"] = (
            "avg_power_units",
            "Average Power Units",
        )

    if "avg_dqs" in state_agg.columns:
        metric_options["Average Data Quality Score (DQS)"] = (
            "avg_dqs",
            "Average Data Quality Score (DQS)",
        )

    if "InsurancePct" in state_agg.columns:
        metric_options["Percent with Insurance History"] = (
            "InsurancePct",
            "% with Insurance History",
        )
    if "VerifiedPct" in state_agg.columns:
        metric_options["Percent with Verified Addresses"] = (
            "VerifiedPct",
            "% Verified Addresses",
        )

    # ------------------------------------------------------------------
    # LEFT COLUMN: Nationwide map (filtered vs filtered-out states)
    # ------------------------------------------------------------------
    with col_map:
        st.subheader("Nationwide Metrics")
        st.caption(f"Geographic filters: {geo_summary}")

        selected_metric_label = st.selectbox(
            "Choropleth Metric",
            options=list(metric_options.keys()),
            index=0,
        )
        metric_col, metric_title = metric_options[selected_metric_label]

        # Build a mapping dataframe that includes every allowed state code
        # (even if the current filters removed all companies from that state).
        # "states" comes from the sidebar filter setup.
        map_states = states
        map_df = pd.DataFrame({"State": map_states})

        # Attach the selected metric from state_agg where it exists.
        if not state_agg.empty and metric_col in state_agg.columns:
            map_df = map_df.merge(
                state_agg[["State", metric_col]],
                on="State",
                how="left",
            )
        else:
            map_df[metric_col] = np.nan

        # Determine which states are explicitly excluded by the geographic
        # filters (state selection, West-of-Mississippi, exclude AK/HI/NY/NJ).
        geo_allowed_states = set(map_states)

        if west_only:
            geo_allowed_states &= west_states

        if selected_states:
            geo_allowed_states &= set(selected_states)

        if exclude_special:
            geo_allowed_states -= {"AK", "HI", "NJ", "NY"}

        map_df["geo_allowed"] = map_df["State"].isin(geo_allowed_states)

        # Metric used for coloring:
        # - States that are still allowed by the geographic filters but have
        #   no remaining companies get a value of 0 so they appear in the
        #   normal color scale.
        # - States that are geo-filtered-out get NaN and are drawn in gray.
        map_df["MetricForMap"] = np.where(
            map_df["geo_allowed"],
            map_df[metric_col],
            np.nan,
        )

        # For geo-allowed states with no data, treat the metric as zero.
        map_df.loc[
            map_df["geo_allowed"] & map_df["MetricForMap"].isna(),
            "MetricForMap",
        ] = 0.0

        # Pre-format hover text:
        #   - Explicitly excluded states: "Filtered Out"
        #   - Included states: show the metric value (0 is allowed)
        def _format_hover(row):
            if not row["geo_allowed"]:
                return "Filtered Out"
            val = row["MetricForMap"]
            if metric_col in ["CompanyCount", "InsuranceCount"]:
                return f"{metric_title}: {val:,.0f}"
            else:
                return f"{metric_title}: {val:,.2f}"

        map_df["HoverText"] = map_df.apply(_format_hover, axis=1)

        inactive_df = map_df[~map_df["geo_allowed"]]
        active_df = map_df[map_df["geo_allowed"]]

        fig = go.Figure()

        # Base layer: states that are filtered out (light gray, thin border)
        if not inactive_df.empty:
            fig.add_trace(
                go.Choropleth(
                    locations=inactive_df["State"],
                    locationmode="USA-states",
                    z=[0] * len(inactive_df),  # dummy values for color scale
                    colorscale=[[0, "#e0e0e0"], [1, "#e0e0e0"]],
                    showscale=False,
                    hovertemplate="<b>%{location}</b><br>Filtered Out<extra></extra>",
                    marker=dict(
                        line=dict(color="rgba(120,120,120,0.5)", width=0.5),
                    ),
                )
            )

        # Top layer: states that remain after filters (Blues, darker border)
        if not active_df.empty:
            active_z = active_df["MetricForMap"].astype(float)

            fig.add_trace(
                go.Choropleth(
                    locations=active_df["State"],
                    locationmode="USA-states",
                    z=active_z,
                    colorscale="Blues",
                    colorbar=dict(
                        title=metric_title,
                        x=1.01,
                        y=0.5,
                        len=0.8,
                        thickness=12,
                    ),
                    text=active_df["HoverText"],
                    hovertemplate="<b>%{location}</b><br>%{text}<extra></extra>",
                    marker=dict(
                        line=dict(color="black", width=1.5),
                    ),
                )
            )

            # Adjust numeric formatting in the colorbar ticks
            if metric_col in ["CompanyCount", "InsuranceCount"]:
                fig.data[-1].colorbar.tickformat = ",d"
            else:
                fig.data[-1].colorbar.tickformat = ",.2f"

            # If only one state remains, stretch the color scale from 0 to its value
            if len(active_df) == 1:
                single_val = float(active_z.iloc[0])
                fig.data[-1].zmin = 0.0
                fig.data[-1].zmax = single_val

        # Shared map layout for both layers
        fig.update_geos(
            scope="usa",
            projection_type="albers usa",
            showcountries=False,
            showsubunits=False,
            showlakes=False,
            showcoastlines=False,
        )

        fig.update_layout(
            height=420,
            margin=dict(l=0, r=0, t=10, b=0),
        )

        if active_df.empty and inactive_df.empty:
            st.info("No state data available for current filters.")
        else:
            st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # RIGHT COLUMN: County view (single state) or Top 10 states bar chart
    # ------------------------------------------------------------------
    with col_map_right:
        unique_states = source_for_map["phy_state"].dropna().unique()

        # When exactly one state is selected, show a ZCTA-level map
        if len(unique_states) == 1 and "phy_zip" in source_for_map.columns:
            state_abbr = unique_states[0]

            st.subheader(f"ZCTA Metrics – {state_abbr}")

            if not state_abbr:
                st.info("No ZCTA mapping available for this state.")
            else:
                if metric_col == "VerifiedPct":
                    # In this special case, county-level verified percentages
                    # can be misleading and are explained in text instead.
                    st.markdown(
                        "<div style='height:330px'></div>", unsafe_allow_html=True
                    )

                    missing_zcta_rows = source_for_map[
                        (source_for_map["phy_state"] == state_abbr)
                        & source_for_map["phy_zip"].isna()
                    ]

                    st.caption(
                        f"County-level % Verified is not shown because it provides little additional insight. "
                        f"It can only be calculated for companies in {state_abbr} that have both a verified "
                        f"address and a known county. {len(missing_zcta_rows):,} companies in {state_abbr} "
                        f"lack county information and would be excluded, which makes all counties "
                        f"be 100% verified even when the statewide percentage is lower."
                    )

                else:
                    # Add a spacer so the county map lines up visually with the national map
                    st.markdown(
                        "<div style='height:120px'></div>", unsafe_allow_html=True
                    )

                    state_df = source_for_map[
                        (source_for_map["phy_state"] == state_abbr)
                        & (source_for_map["phy_zip"].notna())
                    ]

                    base_zctas = get_state_zcta_frame(state_abbr)
                    if base_zctas.empty:
                        st.info("No ZCTA shapes found for this state.")
                    else:
                        zcta_counts = base_zctas.copy()
                        metric_series = None

                        # Aggregate the selected metric at the county level
                        if not state_df.empty:
                            by_zcta = state_df.groupby("phy_zip")

                            if metric_col == "CompanyCount":
                                metric_series = (
                                    by_zcta["phy_zip"].size().rename("MetricValue")
                                )
                            elif (
                                metric_col == "avg_company_fit_score"
                                and "company_fit_score" in state_df.columns
                            ):
                                metric_series = (
                                    by_zcta["company_fit_score"]
                                    .mean()
                                    .rename("MetricValue")
                                )

                            elif (
                                metric_col == "avg_recent_mileage"
                                and "recent_mileage" in state_df.columns
                            ):
                                metric_series = (
                                    by_zcta["recent_mileage"]
                                    .mean()
                                    .rename("MetricValue")
                                )

                            elif (
                                metric_col == "avg_drivers"
                                and "driver_total" in state_df.columns
                            ):
                                metric_series = (
                                    by_zcta["driver_total"].mean().rename("MetricValue")
                                )

                            elif (
                                metric_col == "avg_power_units"
                                and "nbr_power_unit" in state_df.columns
                            ):
                                metric_series = (
                                    by_zcta["nbr_power_unit"]
                                    .mean()
                                    .rename("MetricValue")
                                )

                            elif (
                                metric_col == "InsuranceCount"
                                and "num_filings" in state_df.columns
                            ):
                                metric_series = (
                                    by_zcta["num_filings"]
                                    .apply(lambda s: s.notna().sum())
                                    .rename("MetricValue")
                                )

                            elif (
                                metric_col == "InsurancePct"
                                and "num_filings" in state_df.columns
                            ):
                                counts = by_zcta["phy_zip"].size()
                                ins_counts = by_zcta["num_filings"].apply(
                                    lambda s: s.notna().sum()
                                )
                                pct = np.where(
                                    counts > 0,
                                    ins_counts / counts * 100.0,
                                    np.nan,
                                )
                                metric_series = pd.Series(
                                    pct,
                                    index=counts.index,
                                    name="MetricValue",
                                )

                            elif metric_col == "avg_dqs" and "dqs" in state_df.columns:
                                metric_series = (
                                    by_zcta["dqs"].mean().rename("MetricValue")
                                )

                        # Attach metric values (if any) to the full list of counties
                        if metric_series is not None:
                            metric_df = metric_series.reset_index()
                            # .rename(
                            #     columns={"county_fips": "county_fips"}
                            # )
                            zcta_counts = zcta_counts.merge(
                                metric_df,
                                on="phy_zip",
                                how="left",
                            )
                        else:
                            # No metric for this selection -> start with all NaN
                            zcta_counts["MetricValue"] = np.nan

                        # Determine which counties are explicitly excluded by the
                        # geography filters (county multiselect). If no counties
                        # are selected, all counties in the state are considered
                        # geo-allowed.
                        if selected_zips:
                            allowed = set(selected_zips)
                            zcta_counts["geo_allowed"] = zcta_counts["phy_zip"].isin(
                                allowed
                            )
                        else:
                            zcta_counts["geo_allowed"] = True

                        # Metric used for coloring:
                        # - ZCTAS that are still allowed by the geographic
                        # filters
                        #   but have no remaining companies get a value of 0 so they
                        #   appear in the normal color scale.
                        # - ZCTAs that are geo-filtered-out get NaN and are
                        # drawn
                        #   in gray.
                        zcta_counts["MetricForMap"] = np.where(
                            zcta_counts["geo_allowed"],
                            zcta_counts["MetricValue"],
                            np.nan,
                        )

                        zcta_counts.loc[
                            zcta_counts["geo_allowed"]
                            & zcta_counts["MetricForMap"].isna(),
                            "MetricForMap",
                        ] = 0.0

                        # Build human-readable hover text
                        def _format_zcta_hover(row):
                            if not row["geo_allowed"]:
                                return "Filtered Out"
                            val = row["MetricForMap"]
                            if metric_col in ["CompanyCount", "InsuranceCount"]:
                                return f"{metric_title}: {val:,.0f}"
                            else:
                                return f"{metric_title}: {val:,.2f}"

                        zcta_counts["HoverText"] = zcta_counts.apply(
                            _format_zcta_hover,
                            axis=1,
                        )

                        inactive_df = zcta_counts[~zcta_counts["geo_allowed"]]
                        active_df = zcta_counts[zcta_counts["geo_allowed"]]

                        zcta_geojson = state_zctas_geojson(state_abbr)

                        fig_zcta = go.Figure()

                        # ------------------------------------------------------
                        # Base layer: counties with no data after filters
                        # (light gray, thin border, "Filtered Out" hover)
                        # ------------------------------------------------------
                        if not inactive_df.empty:
                            fig_zcta.add_trace(
                                go.Choropleth(
                                    geojson=zcta_geojson,
                                    locations=inactive_df["phy_zip"],
                                    featureidkey="properties.GEOID20",
                                    z=[0] * len(inactive_df),
                                    colorscale=[[0, "#e0e0e0"], [1, "#e0e0e0"]],
                                    showscale=False,
                                    customdata=inactive_df[["phy_zip"]].to_numpy(),
                                    hovertemplate=(
                                        "%{customdata[0]}<br>Filtered Out<extra></extra>"
                                    ),
                                    marker=dict(
                                        line=dict(
                                            color="rgba(120,120,120,0.5)",
                                            width=0.5,
                                        )
                                    ),
                                )
                            )

                        # ------------------------------------------------------
                        # Top layer: counties that remain after filters
                        # (Blues scale, darker border, metric value in hover)
                        # ------------------------------------------------------
                        if not active_df.empty:
                            active_z = active_df["MetricForMap"].astype(float)

                            fig_zcta.add_trace(
                                go.Choropleth(
                                    geojson=zcta_geojson,
                                    locations=active_df["phy_zip"],
                                    featureidkey="properties.GEOID20",
                                    z=active_z,
                                    colorscale="Blues",
                                    colorbar=dict(
                                        title=metric_title,
                                        x=1.01,
                                        y=0.5,
                                        len=0.8,
                                        thickness=12,
                                    ),
                                    customdata=active_df[["phy_zip"]].to_numpy(),
                                    text=active_df["HoverText"],
                                    hovertemplate=(
                                        "%{customdata[0]}<br>%{text}<extra></extra>"
                                    ),
                                    marker=dict(
                                        line=dict(
                                            color="rgba(100, 100, 100, 0.6)", width=0.25
                                        ),
                                    ),
                                )
                            )

                            # Match numeric formatting with the state-level map
                            if metric_col in ["CompanyCount", "InsuranceCount"]:
                                fig_zcta.data[-1].colorbar.tickformat = ",d"
                            else:
                                fig_zcta.data[-1].colorbar.tickformat = ",.2f"

                        # Shared layout for county map
                        fig_zcta.update_geos(
                            fitbounds="locations",
                            visible=False,
                        )

                        fig_zcta.update_layout(
                            height=420,
                            margin=dict(l=0, r=0, t=10, b=0),
                        )

                        if active_df.empty and inactive_df.empty:
                            st.info("No ZCTA data available for current filters.")
                        else:
                            st.plotly_chart(fig_zcta, use_container_width=True)

        # If multiple states are selected, show a Top 10 bar chart instead
        else:
            if not state_agg.empty:
                st.subheader("Top States")

                top10 = state_agg.sort_values(metric_col, ascending=False).head(10)

                vmin = state_agg[metric_col].min()
                vmax = state_agg[metric_col].max()
                colorscale = px.colors.sequential.Blues

                # Convert metric values into colors aligned with the choropleth colorscale
                def value_to_color(v):
                    if vmax == vmin:
                        t = 0.5
                    else:
                        t = (v - vmin) / (vmax - vmin)
                    t = float(max(0.0, min(1.0, t)))
                    color_list = px.colors.sample_colorscale(colorscale, [t])
                    return color_list[0] if color_list else colorscale[0]

                bar_colors = [value_to_color(v) for v in top10[metric_col]]

                fig_bar = px.bar(
                    top10,
                    x="State",
                    y=metric_col,
                    labels={"State": "State", metric_col: metric_title},
                )

                fig_bar.update_traces(marker_color=bar_colors)

                # Use integer formatting for counts and 2-decimal formatting otherwise
                if metric_col in ["CompanyCount", "InsuranceCount"]:
                    fig_bar.update_yaxes(tickformat=",d")
                    bar_hover = (
                        "State: %{x}<br>"
                        f"{metric_title}: " + "%{y:,.0f}<extra></extra>"
                    )
                else:
                    fig_bar.update_yaxes(tickformat=",.2f")
                    bar_hover = (
                        "State: %{x}<br>"
                        f"{metric_title}: " + "%{y:,.2f}<extra></extra>"
                    )

                fig_bar.update_traces(hovertemplate=bar_hover)

                fig_bar.update_layout(
                    height=520,
                    margin=dict(l=0, r=0, t=10, b=0),
                )

                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("No state data available for current filters.")


# ----------------------------------------------------------------------
# Fleet metrics & Fit Score Distribution
# ----------------------------------------------------------------------
st.subheader("Fleet Metrics & Fit Score Distribution")

col_hist, col_units, col_drivers, col_miles = st.columns(4)

# ------------------------------------------------------------
# Fit Score Histogram
# ------------------------------------------------------------
with col_hist:
    if "company_fit_score" in filtered_df.columns:
        s = pd.to_numeric(filtered_df["company_fit_score"], errors="coerce").dropna()

        if not s.empty:
            bin_size = 0.05
            bins = np.arange(0.0, 1.0 + bin_size, bin_size)

            counts, edges = np.histogram(s, bins=bins)
            centers = (edges[:-1] + edges[1:]) / 2.0
            median_fit = float(s.median())

            hist_df = pd.DataFrame(
                {
                    "BinCenter": centers,
                    "Count": counts,
                    "BinStart": edges[:-1],
                    "BinEnd": edges[1:],
                }
            )

            fig_fit = px.bar(
                hist_df,
                x="BinCenter",
                y="Count",
                title="Fit Scores",
                labels={"BinCenter": "Company Fit Score", "Count": "Count"},
            )

            fig_fit.update_traces(
                customdata=hist_df[["BinStart", "BinEnd"]],
                hovertemplate=(
                    "Range: %{customdata[0]:.2f}–%{customdata[1]:.2f}<br>"
                    "Count: %{y:,.0f}<extra></extra>"
                ),
                marker_line_color="black",
                marker_line_width=1.5,
            )

            max_count = int(hist_df["Count"].max())
            fig_fit.add_scatter(
                x=[median_fit, median_fit],
                y=[0, max_count],
                mode="lines",
                line=dict(color="red", width=2, dash="dash"),
                hovertemplate=f"Median: {median_fit:.2f}<extra></extra>",
                showlegend=False,
            )

            fig_fit.update_xaxes(range=[0, 1])
            fig_fit.update_yaxes(tickformat=",d")
            fig_fit.update_layout(height=300, margin=dict(l=20, r=10, t=60, b=10))

            st.plotly_chart(fig_fit, use_container_width=True)


# ------------------------------------------------------------
# Helper: segmented fleet distributions (business-friendly bins)
# ------------------------------------------------------------
def plot_segmented_metric(
    df_in,
    col: str,
    title: str,
    x_label: str,
    bins,
    labels,
    container,
    exclude_zero: bool = False,
):
    """
    Plot the distribution of a numeric column using business-friendly
    segments (for example: 1–5, 6–20, 21–50, etc.), and show the
    percentage of companies in each segment.

    Args:
        df_in: DataFrame containing the column to segment.
        col: Name of the numeric column to analyze.
        title: Chart title.
        x_label: Label to use on the x-axis and in hover text.
        bins: List of numeric bin edges to define segments.
        labels: Labels corresponding to each bin interval.
        container: Streamlit container in which the plot will be rendered.
        exclude_zero: If True, rows with zero values in 'col' are excluded.
    """
    if col not in df_in.columns:
        return

    s = pd.to_numeric(df_in[col], errors="coerce").dropna()
    if exclude_zero:
        s = s[s != 0]

    if s.empty:
        with container:
            st.info(f"No valid data to display for {title}.")
        return

    cat = pd.cut(
        s,
        bins=bins,
        labels=labels,
        right=True,
        include_lowest=True,
    )

    seg_counts = (
        cat.value_counts()
        .reindex(labels)  # keep segment order stable
        .fillna(0)
        .rename_axis("Segment")
        .reset_index(name="Count")
    )
    seg_counts["Percent"] = seg_counts["Count"] / seg_counts["Count"].sum() * 100.0

    # Drop leading empty segments so we don't show bars for ranges that are
    # completely excluded by the current filters (e.g., 1–4 drivers when
    # the filter is set to min 5).
    nonzero_indices = np.where(seg_counts["Count"].to_numpy() > 0)[0]
    if len(nonzero_indices) > 0:
        first_idx = nonzero_indices[0]
        last_idx = nonzero_indices[-1]
        seg_counts = seg_counts.iloc[first_idx : last_idx + 1].copy()

    fig = px.bar(
        seg_counts,
        x="Segment",
        y="Count",
        title=title,
        labels={"Segment": x_label, "Count": "Companies"},
    )

    fig.update_traces(
        customdata=seg_counts[["Percent"]].to_numpy(),
        hovertemplate=(
            f"{x_label}: %{{x}}<br>"
            "Companies: %{y:,.0f}<br>"
            "Share: %{customdata[0]:.1f}%<extra></extra>"
        ),
        marker_line_color="black",
        marker_line_width=1.5,
    )

    # Ensure all segments appear on the x-axis in the intended order
    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=labels,
    )

    fig.update_yaxes(tickformat=",d")
    fig.update_layout(height=300, margin=dict(l=20, r=10, t=60, b=10))

    with container:
        st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------
# Segmented Power Units Distribution
# ------------------------------------------------------------
# Always show 7 buckets, and re-bin dynamically as the user increases
# the minimum power units filter. The categories slide upward so that
# we never waste bars on ranges that are completely filtered out.
min_units_current = st.session_state.get("min_units", 1)

if min_units_current <= 1:
    # Default view:
    # 1, 2, 3, 4, 5, 6–9, 10+
    power_bins = [0, 1, 2, 3, 4, 5, 9, np.inf]
    power_labels = ["1", "2", "3", "4", "5", "6–9", "10+"]
elif min_units_current == 2:
    # Min = 2:
    # 2, 3, 4, 5, 6, 7–9, 10+
    power_bins = [0, 2, 3, 4, 5, 6, 9, np.inf]
    power_labels = ["2", "3", "4", "5", "6", "7–9", "10+"]
elif min_units_current == 3:
    # Min = 3:
    # 3, 4, 5, 6, 7, 8–9, 10+
    power_bins = [0, 3, 4, 5, 6, 7, 9, np.inf]
    power_labels = ["3", "4", "5", "6", "7", "8–9", "10+"]
else:
    # From min >= 4 onward, use a sliding window of 6 single-value
    # buckets plus a "catch-all" 7th bucket:
    #
    # Example: min = 4  ->  4, 5, 6, 7, 8, 9, 10+
    #          min = 5  ->  5, 6, 7, 8, 9, 10, 11+
    #          min = 6  ->  6, 7, 8, 9, 10, 11, 12+
    #
    start = int(min_units_current)
    edges = [start + i for i in range(0, 6)]  # start, start+1, ... start+5
    power_bins = [0] + edges + [np.inf]
    power_labels = [str(start + i) for i in range(0, 6)] + [f"{start + 6}+"]

plot_segmented_metric(
    filtered_df,
    col="nbr_power_unit",
    title="Fleet Size (by Power Units)",
    x_label="Power Units",
    bins=power_bins,
    labels=power_labels,
    container=col_units,
)

# ------------------------------------------------------------
# Segmented Drivers Distribution
# ------------------------------------------------------------
# Same idea as power units: always show 7 buckets that slide upward as
# the minimum drivers filter increases.
min_drivers_current = st.session_state.get("min_drivers", 1)

if min_drivers_current <= 1:
    # Default view:
    # 1, 2, 3, 4, 5, 6–9, 10+
    driver_bins = [0, 1, 2, 3, 4, 5, 9, np.inf]
    driver_labels = ["1", "2", "3", "4", "5", "6–9", "10+"]
elif min_drivers_current == 2:
    # Min = 2:
    # 2, 3, 4, 5, 6, 7–9, 10+
    driver_bins = [0, 2, 3, 4, 5, 6, 9, np.inf]
    driver_labels = ["2", "3", "4", "5", "6", "7–9", "10+"]
elif min_drivers_current == 3:
    # Min = 3:
    # 3, 4, 5, 6, 7, 8–9, 10+
    driver_bins = [0, 3, 4, 5, 6, 7, 9, np.inf]
    driver_labels = ["3", "4", "5", "6", "7", "8–9", "10+"]
else:
    # From min >= 4 onward, slide a 6-value window plus a final "N+"
    # bucket, analogous to the power units distribution.
    #
    # Example: min = 4  ->  4, 5, 6, 7, 8, 9, 10+
    #          min = 5  ->  5, 6, 7, 8, 9, 10, 11+
    #          min = 6  ->  6, 7, 8, 9, 10, 11, 12+
    #
    start = int(min_drivers_current)
    edges = [start + i for i in range(0, 6)]  # start, start+1, ... start+5
    driver_bins = [0] + edges + [np.inf]
    driver_labels = [str(start + i) for i in range(0, 6)] + [f"{start + 6}+"]

plot_segmented_metric(
    filtered_df,
    col="driver_total",
    title="Fleet Size (by Drivers)",
    x_label="Drivers",
    bins=driver_bins,
    labels=driver_labels,
    container=col_drivers,
)


# ------------------------------------------------------------
# Segmented Recent Mileage Distribution
# ------------------------------------------------------------
# Start with fixed buckets:
#   1–1k, 1k–10k, 10k–50k, 50k–100k, 100k–250k, 250k–500k, 500k+
# As the minimum mileage filter increases and entire buckets are
# filtered out, we drop those bins from the left and grow the
# upper end with 250k-wide ranges, but only switch to fully
# generic 250k bands once the minimum reaches 250k.
min_miles_current = st.session_state.get("mileage_min", miles_min)

if min_miles_current < 1_000:
    # Base case: 7 buckets
    miles_bins = [0, 1_000, 10_000, 50_000, 100_000, 250_000, 500_000, np.inf]
    miles_labels = [
        "1–1k",
        "1k–10k",
        "10k–50k",
        "50k–100k",
        "100k–250k",
        "250k–500k",
        "500k+",
    ]
elif min_miles_current < 10_000:
    # Drop 1–1k, add 500k–750k and 750k+
    miles_bins = [1_000, 10_000, 50_000, 100_000, 250_000, 500_000, 750_000, np.inf]
    miles_labels = [
        "1k–10k",
        "10k–50k",
        "50k–100k",
        "100k–250k",
        "250k–500k",
        "500k–750k",
        "750k+",
    ]
elif min_miles_current < 50_000:
    # Drop 1k–10k as well; add 750k–1M and 1M+
    miles_bins = [10_000, 50_000, 100_000, 250_000, 500_000, 750_000, 1_000_000, np.inf]
    miles_labels = [
        "10k–50k",
        "50k–100k",
        "100k–250k",
        "250k–500k",
        "500k–750k",
        "750k–1M",
        "1M+",
    ]
elif min_miles_current < 100_000:
    # Drop 10k–50k; keep 50k–100k & 100k–250k, expand high end
    miles_bins = [
        50_000,
        100_000,
        250_000,
        500_000,
        750_000,
        1_000_000,
        1_250_000,
        np.inf,
    ]
    miles_labels = [
        "50k–100k",
        "100k–250k",
        "250k–500k",
        "500k–750k",
        "750k–1M",
        "1M–1.25M",
        "1.25M+",
    ]
elif min_miles_current < 250_000:
    # Drop 50k–100k once min >= 100k; keep 100k–250k then 250k+
    miles_bins = [
        100_000,
        250_000,
        500_000,
        750_000,
        1_000_000,
        1_250_000,
        1_500_000,
        np.inf,
    ]
    miles_labels = [
        "100k–250k",
        "250k–500k",
        "500k–750k",
        "750k–1M",
        "1M–1.25M",
        "1.25M–1.5M",
        "1.5M+",
    ]
else:
    # For higher minimums (>= 250k), continue the pattern generically:
    # 7 consecutive 250k-wide bands starting at the nearest lower
    # multiple of 250k, plus a final open-ended bucket.
    step = 250_000
    start = int((min_miles_current // step) * step)

    # Construct 7 edges: [start, start+step, ..., start+6*step]
    edges = [start + step * i for i in range(0, 7)]
    miles_bins = edges + [np.inf]

    def _fmt(v: int) -> str:
        if v >= 1_000_000:
            x = v / 1_000_000
            if x.is_integer():
                return f"{int(x)}M"
            return f"{x:.2f}M".rstrip("0").rstrip(".")
        else:
            return f"{v // 1_000}k"

    miles_labels = []
    for i in range(0, 6):
        lo = edges[i]
        hi = edges[i + 1]
        miles_labels.append(f"{_fmt(lo)}–{_fmt(hi)}")
    last_lo = edges[6]
    miles_labels.append(f"{_fmt(last_lo)}+")

plot_segmented_metric(
    filtered_df,
    col="recent_mileage",
    title="Recent Mileage (by Segment)",
    x_label="Annual Mileage",
    bins=miles_bins,
    labels=miles_labels,
    container=col_miles,
    exclude_zero=True,  # exclude rows with zero mileage so this chart reflects active mileage
)

# ----------------------------------------------------------------------
# Company list + search + download
# ----------------------------------------------------------------------

# Work on a copy of the filtered dataset for searching, previewing, and export
table_df = filtered_df.copy()

st.subheader("Company List Search (within filtered set)")

# -------------------------------
# DOT Number search + clear (✕)
# -------------------------------
outer_dot_col, _ = st.columns([2, 3])  # make the search area narrower than full width
with outer_dot_col:
    dot_main_col, dot_clear_col = st.columns([4, 1])

    # Button is defined first so it can safely update session_state
    with dot_clear_col:
        if st.button("✕", key="clear_dot_search", help="Clear DOT search"):
            st.session_state["dot_search"] = ""

    with dot_main_col:
        dot_search = st.text_input(
            "Search by DOT Number (exact)",
            key="dot_search",
            help="Enter a full DOT number to find a specific carrier. Must be an exact match.",
        )

# --------------------------------
# Company Name search + clear (✕)
# --------------------------------
outer_name_col, _ = st.columns([2, 3])  # also narrower
with outer_name_col:
    name_main_col, name_clear_col = st.columns([4, 1])

    # Button first so it can safely clear the value before the widget is built
    with name_clear_col:
        if st.button("✕", key="clear_name_search", help="Clear name search"):
            st.session_state["name_search"] = ""

    with name_main_col:
        name_search = st.text_input(
            "Search by Company Name",
            key="name_search",
            help="Case-insensitive search that matches any part of the company legal name.",
        )

# Apply DOT and name search constraints on top of all other filters
if not table_df.empty:
    search_mask = pd.Series(True, index=table_df.index)

    if dot_search.strip() and "dot_number" in table_df.columns:
        search_mask &= table_df["dot_number"].astype(str) == dot_search.strip()

    if name_search.strip() and "legal_name" in table_df.columns:
        search_mask &= (
            table_df["legal_name"]
            .astype(str)
            .str.contains(name_search.strip(), case=False, na=False)
        )

    table_df = table_df[search_mask]


# Mapping from internal column names to human-friendly labels for display/export
full_rename = {
    "dot_number": "DOT Number",
    "company_fit_score": "Company Fit Score",
    "prospect_status": "Prospect Status",
    "legal_name": "Company Legal Name",
    "dba_name": "Doing Business As Name",
    "email_address": "Email Address",
    "telephone": "Phone Number",
    "phy_state": "Physical State",
    "carrier_operation": "Carrier Type",
    "hm_flag": "Hazardous Material",
    "pc_flag": "Passenger Carrier",
    "phy_street": "Street (Physical)",
    "phy_city": "City (Physical)",
    "phy_zip": "ZIP Code (Physical)",
    "phy_country": "Country (Physical)",
    "mailing_street": "Street (Mailing)",
    "mailing_city": "City (Mailing)",
    "mailing_state": "State (Mailing)",
    "mailing_zip": "ZIP Code (Mailing)",
    "mailing_country": "Country (Mailing)",
    "fax": "Fax Number",
    "cargo_carried": "Cargo Carried",
    "cargo_categorized": "Cargo Categories",
    "mcs150_date": "MCS-150 Filing Date",
    "mcs150_mileage": "MCS-150 Mileage",
    "mcs150_mileage_year": "MCS-150 Year",
    "add_date": "Date Data Added",
    "oic_state": "FMCSA State",
    "nbr_power_unit": "Number of Power Units",
    "driver_total": "Number of Drivers",
    "recent_mileage": "Recent Mileage",
    "recent_mileage_year": "Recent Mileage Year",
    "vmt_source_id": "Mileage Reporting Source",
    "private_only": "Private Carrier",
    "exempt_for_hire": "Exempt For Hire",
    "authorized_for_hire": "Authorized for Hire",
    "private_property": "Private Property",
    "private_passenger_business": "Private Passenger Business",
    "private_passenger_nonbusiness": "Private Passenger Non-Business",
    "migrant": "Migrant",
    "us_mail": "US Mail",
    "federal_government": "Federal Government",
    "state_government": "State Government",
    "local_government": "Local Government",
    "indian_tribe": "Indian Tribe",
    "op_other": "Other Operator",
    "num_filings": "Total Insurance Filings",
    "num_unique_companies": "Insurance Companies Used",
    "top_company": "Most Used Insurance Company",
    "top_company_share": "Share of Filings with Top Company",
    "cancelled_method_count": "Cancellation Count",
    "replaced_method_count": "Replacement Count",
    "name_changed_method_count": "Name Change Count",
    "transferred_method_count": "Transfer Count",
    "first_filing_date": "First Filing Date",
    "last_filing_date": "Latest Filing Date",
    "all_companies": "All Insurance Companies Used",
    "count_cargo": "Cargo Policy Count",
    "count_bipd": "Bi&PD Policy Count",
    "count_broker_bond": "Broker Bond Count",
    "count_broker_trust_fund": "Broker Trust Fund Count",
    "min_gap_days": "Min Days Between Filings",
    "max_gap_days": "Max Days Between Filings",
    "median_gap_days": "Median Days Between Filings",
    "avg_gap_days": "Mean Days Between Filings",
    "total_crashes": "Total Crashes",
    "total_at_fault_crashes": "Total At-Fault Crashes",
    "pct_at_fault": "Percent At-Fault",
    "fars_total": "FARS Total Crashes",
    "fars_at_fault": "FARS Total At-Fault Crashes",
    "fars_pct_at_fault": "FARS Percent At-Fault",
    "crss_total": "CRSS Total Crashes",
    "crss_at_fault": "CRSS Total At-Fault Crashes",
    "crss_pct_at_fault": "CRSS Percent At-Fault",
    "rate_per_100_trucks": "Accidents per 100 Trucks",
    "rate_at_fault_per_100_trucks": "At-Fault Accidents per 100 Trucks",
    "rate_per_100_drivers": "Accidents per 100 Drivers",
    "rate_at_fault_per_100_drivers": "At-Fault Accidents per 100 Drivers",
    "rate_per_1m_miles": "Accidents per 1 Million Miles",
    "rate_at_fault_per_1m_miles": "At-Fault Accidents per 1 Million Miles",
    "fars_rate_per_100_trucks": "FARS Accidents per 100 Trucks",
    "fars_rate_per_100_drivers": "FARS Accidents per 100 Drivers",
    "fars_rate_per_1m_miles": "FARS Accidents per 1 Million Miles",
    "safety_index": "Safety Index",
    "input_address": "Input Address (Geocoding)",
    "match_status": "Address Match Status",
    "match_type": "Match Type",
    "matched_address": "Matched Address (Geocoding)",
    "tiger_line_id": "TIGER/Line ID",
    "side": "Side",
    "lat": "Latitude",
    "lon": "Longitude",
    "county_fips": "County FIPS",
    "county_name": "County Name",
    "county_statefp": "State FIPS",
}

# Default base columns to show in the preview table, if available
base_display_cols = [
    "dot_number",
    "company_fit_score",
    "prospect_status",
    "legal_name",
    "dba_name",
    "email_address",
    "telephone",
    "phy_street",
    "phy_city",
    "phy_state",
    "phy_zip",
    "mailing_street",
    "mailing_city",
    "mailing_state",
    "mailing_zip",
    "fax",
    "cargo_carried",
    "cargo_categorized",
    "recent_mileage",
    "nbr_power_unit",
    "driver_total",
    "top_company",
    "median_gap_days",
    "safety_index",
    "match_status",
]

base_display_cols = [c for c in base_display_cols if c in table_df.columns]

display_df = table_df[base_display_cols].copy()

# Ensure the rename map always includes a label for 'prospect_status'
full_rename.setdefault("prospect_status", "Prospect Status")

# FMCSA URL column for link rendering in Streamlit's data_editor
if "dot_number" in table_df.columns:
    fm_urls = (
        "https://safer.fmcsa.dot.gov/query.asp?"
        "searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string="
        + table_df.loc[display_df.index, "dot_number"].astype(str)
    )

    # Insert a URL column that Streamlit will render as a hyperlink
    if "company_fit_score" in display_df.columns:
        insert_pos = display_df.columns.get_loc("company_fit_score") + 1
    else:
        insert_pos = 1

    # Name this column "FMCSA Profile" so it can be configured as a LinkColumn
    display_df.insert(insert_pos, "FMCSA Profile", fm_urls)

# Rename all columns for display except "FMCSA Profile", which already has its final name
display_df = display_df.rename(columns=full_rename)

# =======================
#  CSV EXPORT (with column order)
# =======================
if len(table_df) == 0:
    st.info(
        "No companies match the current filters and search, so there is nothing to download."
    )
else:
    max_export = len(table_df)
    default_export = min(200, max_export)

    col_export, _ = st.columns([1, 3])
    with col_export:
        st.markdown(
            "<div style='font-size:18px; font-weight:600; margin-bottom:4px;'>"
            "Number of top companies to download"
            "</div>",
            unsafe_allow_html=True,
        )

        export_n = st.number_input(
            label="Number of top companies to download",  # non-empty for accessibility
            label_visibility="collapsed",  # hides the built-in label
            min_value=1,
            max_value=max_export,
            value=default_export,
            step=50,
            key="export_n",
        )

    # Take the first N rows of the filtered and searched table
    full_export_df = table_df.head(export_n).copy()

    # Add an Excel hyperlink formula that links to each company's FMCSA profile
    if "dot_number" in full_export_df.columns:
        full_export_df["FMCSA Link"] = (
            '=HYPERLINK("https://safer.fmcsa.dot.gov/query.asp?'
            "searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string="
            + full_export_df["dot_number"].astype(str)
            + '","FMCSA Profile")'
        )

    # Apply the human-readable column names to the export DataFrame
    renamed_export_df = full_export_df.rename(columns=full_rename)

    # -----------------------------------------
    # Order columns in the CSV:
    # First 8 columns mirror the first 8 of the displayed table (when present),
    # followed by all remaining columns.
    # -----------------------------------------
    preview_cols_order = list(display_df.columns[:8])
    all_export_cols = list(renamed_export_df.columns)

    # Only keep preview columns that actually exist in the export DataFrame
    preview_cols_order = [c for c in preview_cols_order if c in all_export_cols]

    remaining_cols = [c for c in all_export_cols if c not in preview_cols_order]
    export_cols = preview_cols_order + remaining_cols

    renamed_export_df = renamed_export_df[export_cols]

    csv_data = renamed_export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=f"⬇️ Download Top {export_n} Companies (Filters + Search) (CSV)",
        data=csv_data,
        file_name=f"drivepoints_top{export_n}_minfit{min_fit:.2f}_filtered.csv",
        mime="text/csv",
    )

    # =======================
    #  PREVIEW TABLE (length tied to export_n)
    # =======================
    st.subheader("Company List with Contact Info Preview")

    shown = min(export_n, len(display_df))
    st.caption(
        f"Showing top {shown:,} of {len(table_df):,} companies "
        f"(after filters and search)."
    )

    preview_df = display_df.head(export_n).copy()

    edited_preview = st.data_editor(
        preview_df,
        num_rows="fixed",
        hide_index=True,  # hide the DataFrame index column for a cleaner table
        column_config={
            "FMCSA Profile": st.column_config.LinkColumn(
                "FMCSA Profile",
                help="Open FMCSA SAFER snapshot in a new tab.",
                display_text="FMCSA Profile",
            ),
            "Prospect Status": st.column_config.SelectboxColumn(
                "Prospect Status",
                options=PROSPECT_STATUS_OPTIONS,
                help="Track your progress with each company.",
                width="medium",
            ),
        },
        # All columns except "Prospect Status" are read-only for the user
        disabled=[c for c in preview_df.columns if c != "Prospect Status"],
        use_container_width=True,
        key="company_preview_editor",
    )

    # Persist prospect status selections from the data editor into session state
    if (
        not edited_preview.empty
        and "Prospect Status" in edited_preview.columns
        and "dot_number" in table_df.columns
    ):
        # Map edited preview rows back to their DOT numbers
        dots_for_rows = table_df.loc[edited_preview.index, "dot_number"].astype(str)
        new_status_map = dict(zip(dots_for_rows, edited_preview["Prospect Status"]))
        st.session_state["prospect_status_map"].update(new_status_map)

        # Re-apply the updated status map to all relevant DataFrames
        status_map = st.session_state["prospect_status_map"]

        if "dot_number" in df.columns:
            df.loc[:, "dot_number"] = df["dot_number"].astype(str)
            df.loc[:, "prospect_status"] = (
                df["dot_number"].map(status_map).fillna("Not Contacted")
            )

        if "dot_number" in filtered_df.columns:
            filtered_df.loc[:, "dot_number"] = filtered_df["dot_number"].astype(str)
            filtered_df.loc[:, "prospect_status"] = (
                filtered_df["dot_number"].map(status_map).fillna("Not Contacted")
            )

        if "dot_number" in table_df.columns:
            table_df.loc[:, "dot_number"] = table_df["dot_number"].astype(str)
            table_df.loc[:, "prospect_status"] = (
                table_df["dot_number"].map(status_map).fillna("Not Contacted")
            )

        # ------------------------------------------------------
        # Commit button: persist prospect_status to STATUS_PATH
        # ------------------------------------------------------
        if st.button("💾 Commit Prospect Status Changes"):
            # Only save rows where the status is not the default ("Not Contacted")
            to_save = (
                df.loc[
                    df["prospect_status"] != "Not Contacted",
                    ["dot_number", "prospect_status"],
                ]
                .dropna(subset=["dot_number"])
                .assign(dot_number=lambda d: d["dot_number"].astype(str))
                .drop_duplicates(subset=["dot_number"], keep="last")
            )

            n_saved = len(to_save)
            to_save.to_parquet(STATUS_PATH, index=False)

            # Store the number of records saved so it can be shown after the commit
            st.session_state["last_commit_count"] = n_saved

            st.success(
                f"Saved {n_saved:,} prospect status records. "
                "These will be reloaded automatically next time."
            )

    # Always show a summary message under the button if there has been at least one commit
    if "last_commit_count" in st.session_state:
        status_filename = os.path.basename(STATUS_PATH)
        st.caption(
            f"Last commit saved {st.session_state['last_commit_count']:,} records "
            f"to `{status_filename}`."
        )
