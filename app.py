import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import json

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
    "Preview of transportation companies, ranked, with easy access to contacts and state trends. "
    "Company Fit Score is randomly generated for prototype."
)

DATA_PATH = "master_file.parquet"

# ------------------------------------------------------------------
# Data loading and one-time transformations
# ------------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """
    Load the master parquet file and perform all transformations that are
    independent of user interaction (run once per session, then cached).

    - Standardizes column names to lowercase.
    - Ensures DOT numbers are strings.
    - Expands carrier_operation codes into readable labels.
    - Normalizes year-like columns for display.
    - Adds a prototype company_fit_score and sorts by that score.
    - Reorders columns so key identification/contact fields appear first.
    """
    df = pd.read_parquet(path)

    # Standardize column names
    df.columns = df.columns.str.lower()

    # DOT number as string (preserves leading zeros)
    if "dot_number" in df.columns:
        df["dot_number"] = df["dot_number"].astype(str)

    # Map carrier_operation codes to descriptive text where available
    if "carrier_operation" in df.columns:
        df["carrier_operation"] = df["carrier_operation"].map(
            {
                "A": "Interstate",
                "B": "Intrastate Hazmat",
                "C": "Intrastate Non-Hazmat",
            }
        ).fillna(df["carrier_operation"])

    # Normalize mileage year fields so they display cleanly as year strings
    for col in ["mcs150_mileage_year", "recent_mileage_year"]:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce")
                .astype("Int64")
                .astype(str)
            )

    # Prototype fit score for ranking (deterministic via fixed seed)
    np.random.seed(42)
    df["company_fit_score"] = np.round(
        np.random.uniform(0.0, 1.0, size=len(df)),
        3,
    )

    # Bring key columns to the front for convenience; keep all others
    display_columns = [
        "dot_number", "legal_name", "company_fit_score",
        "email_address", "telephone",
    ]
    rest = [c for c in df.columns if c not in display_columns]
    df = df[display_columns + rest]

    # Sort once by company_fit_score so "top companies" is well defined
    df = df.sort_values("company_fit_score", ascending=False)

    return df


df = load_data(DATA_PATH)

# ------------------------------------------------------------------
# GeoJSON loading helpers for county / state maps
# ------------------------------------------------------------------
@st.cache_data
def load_county_geojson():
    """
    Load the nationwide county GeoJSON (cached so it is read from disk
    only once per session).
    """
    with open("tl_2024_us_county.geojson") as f:
        return json.load(f)


@st.cache_data
def load_state_counties_geojson(state_fips: str):
    """
    Return a GeoJSON FeatureCollection containing only the counties
    belonging to a particular state (identified by its FIPS code).

    This is used for the county-level choropleth once a single state
    has been selected in the data.
    """
    full_geojson = load_county_geojson()
    features = [
        feat
        for feat in full_geojson["features"]
        if feat["properties"].get("STATEFP") == state_fips
    ]
    return {"type": "FeatureCollection", "features": features}


@st.cache_data
def get_state_county_lookup(state_fips: str) -> pd.DataFrame:
    """
    Build a small lookup table of counties for a single state from the
    county GeoJSON.

    Returns:
        DataFrame with one row per county, containing:
        - county_fips: combined state + county FIPS code
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
    to NaN. This is cached per (DataFrame, column) to avoid repeated work.

    Returns:
        A numeric Series aligned to df_in.index, or None if the column
        does not exist.
    """
    if col not in df_in.columns:
        return None
    return pd.to_numeric(df_in[col], errors="coerce")


@st.cache_data
def compute_numeric_metadata(df_in: pd.DataFrame) -> dict:
    """
    Pre-compute basic numeric metadata (min, max, 99th percentile) for
    the main numeric columns used in sliders and default ranges.

    This function is called once per session for the loaded DataFrame
    and the returned dictionary is reused throughout the app.
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

# ------------------------------------------------------------------
# Constants / mappings used by multiple sections
# ------------------------------------------------------------------
fit_min = float(df["company_fit_score"].min()) if "company_fit_score" in df.columns else 0.0
fit_max = float(df["company_fit_score"].max()) if "company_fit_score" in df.columns else 1.0

# Default min fit score used in filename when filters are not active
min_fit = 0.0

# User-friendly labels for boolean operation-type flag columns
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

STATE_ABBR_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
}

# Column names reused in several sections
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

    # Exclude non-US state/province codes from the main state filter
    exclude_states = {
        "AB", "AG", "AS", "BC", "BN", "BS", "BZ", "CH", "CI", "CL", "CP", "CR", "CS",
        "DF", "DG", "DO", "FJ", "GB", "GE", "GJ", "GT", "GU", "HD", "HN", "JA", "KW",
        "MB", "MC", "MP", "MR", "MX", "NB", "NL", "NS", "NT", "ON", "PE", "PR", "PU",
        "QC", "QE", "QI", "RO", "SI", "SK", "SL", "SO", "SV", "TA", "TB", "TL", "VC",
        "VI", "YT", "ZA",
    }

    # States considered "west of the Mississippi" for convenience filter
    west_states = {
        "WA", "OR", "CA", "NV", "ID", "ND", "MT", "SD", "MN", "IA",
        "MO", "KS", "NE", "OK", "TX", "AZ", "NM", "CO", "UT",
        "LA", "AR", "WY",
    }

    all_states = sorted(df["phy_state"].dropna().unique())
    states = [s for s in all_states if s not in exclude_states]

    # ------------------------------------------------------------------
    # Precompute ranges for fleet size sliders using numeric_meta
    # ------------------------------------------------------------------
    def get_meta(col, key, default=0):
        """
        Convenience accessor into numeric_meta with a fixed fallback.

        This keeps the logic centralized and makes intent clear where
        numeric ranges are used for UI elements.
        """
        if col in numeric_meta and key in numeric_meta[col]:
            return numeric_meta[col][key]
        return default

    # Recent mileage
    miles_min = int(get_meta(mileage_col, "min", 0))
    miles_max = int(get_meta(mileage_col, "max", 0))
    miles_outlier_cap = get_meta(mileage_col, "q99", None)

    # Drivers
    drivers_min = int(get_meta(drivers_col, "min", 0))
    drivers_max = int(get_meta(drivers_col, "max", 0))
    drivers_outlier_cap = get_meta(drivers_col, "q99", None)

    # Power units
    units_min = int(get_meta(units_col, "min", 0))
    units_max = int(get_meta(units_col, "max", 0))
    units_outlier_cap = get_meta(units_col, "q99", None)

    # UI slider maxes incorporate outlier caps
    miles_ui_max = miles_max if miles_outlier_cap is None else min(miles_max, int(miles_outlier_cap))
    drivers_ui_max = drivers_max if drivers_outlier_cap is None else min(drivers_max, int(drivers_outlier_cap))
    units_ui_max = units_max if units_outlier_cap is None else min(units_max, int(units_outlier_cap))

    # ------------------------------------------------------------------
    # Precompute ranges for insurance / accident columns
    # ------------------------------------------------------------------
    filings_min = int(get_meta(filings_col, "min", 0)) if filings_col in numeric_meta else None
    filings_max = int(get_meta(filings_col, "max", 0)) if filings_col in numeric_meta else None

    insurers_min = int(get_meta(insurers_col, "min", 0)) if insurers_col in numeric_meta else None
    insurers_max = int(get_meta(insurers_col, "max", 0)) if insurers_col in numeric_meta else None

    gap_min = int(get_meta(median_gap_col, "min", 0)) if median_gap_col in numeric_meta else None
    gap_max = int(get_meta(median_gap_col, "max", 0)) if median_gap_col in numeric_meta else None

    total_crashes_max = int(get_meta(total_crashes_col, "max", 0)) if total_crashes_col in numeric_meta else None
    at_fault_crashes_max = int(get_meta(at_fault_crashes_col, "max", 0)) if at_fault_crashes_col in numeric_meta else None
    pct_at_fault_max = float(get_meta(pct_at_fault_col, "max", 0.0)) if pct_at_fault_col in numeric_meta else None

    safety_index_min = float(get_meta(safety_index_col, "min", 0.0)) if safety_index_col in numeric_meta else None
    safety_index_max = float(get_meta(safety_index_col, "max", 0.0)) if safety_index_col in numeric_meta else None

    # ------------------------------------------------------------------
    # Defaults for basic filters (country, mail, hazmat, territories)
    # ------------------------------------------------------------------
    countries = sorted(df["phy_country"].dropna().unique()) if "phy_country" in df.columns else []
    default_country = "US" if "US" in countries else (countries[0] if countries else None)

    mail_options = sorted(df["us_mail"].dropna().unique()) if "us_mail" in df.columns else []
    hm_options = sorted(df["hm_flag"].dropna().unique()) if "hm_flag" in df.columns else []

    default_mail = "N" if "N" in mail_options else (mail_options[0] if mail_options else None)
    default_hm = "N" if "N" in hm_options else (hm_options[0] if hm_options else None)

    # Initialize session_state defaults that need to persist across reruns
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
    # Reset button: clear filters back to consistent defaults
    # ------------------------------------------------------------------
    if st.sidebar.button("Reset filters"):
        # Fit score
        st.session_state["min_fit_score"] = 0.0

        # Geographic filters
        st.session_state["phy_state_selection"] = []
        st.session_state["west_of_mississippi"] = False
        st.session_state["exclude_ak_hi_nj_ny"] = False
        st.session_state["verified_addresses_only"] = False

        # Fleet size filters
        if mileage_col in df.columns:
            st.session_state["mileage_min"] = miles_min
            st.session_state["mileage_max"] = miles_ui_max

        if drivers_col in df.columns:
            st.session_state["min_drivers"] = max(1, drivers_min)
            st.session_state["max_drivers"] = drivers_ui_max

        if units_col in df.columns:
            st.session_state["min_units"] = max(1, units_min)
            st.session_state["max_units"] = units_ui_max

        # Default filters
        if default_country is not None:
            st.session_state["phy_country_selection"] = [default_country]

        if default_mail is not None:
            st.session_state["us_mail_filter"] = default_mail

        if default_hm is not None:
            st.session_state["hm_flag_filter"] = default_hm

        st.session_state["exclude_territories"] = True

        # Outlier caps
        st.session_state["cap_mileage_outliers"] = True
        st.session_state["cap_driver_outliers"] = True
        st.session_state["cap_unit_outliers"] = True

        # Operation type filters
        st.session_state["operation_flags"] = []
        st.session_state["carrier_type_filter"] = []

        # Insurance filters
        st.session_state["has_insurance_info"] = False
        if filings_min is not None and filings_max is not None:
            st.session_state["filings_range"] = (filings_min, filings_max)
        if insurers_min is not None and insurers_max is not None:
            st.session_state["insurers_range"] = (insurers_min, insurers_max)
        if gap_min is not None and gap_max is not None:
            st.session_state["median_gap_min"] = gap_min
            st.session_state["median_gap_max"] = gap_max

        # Accident filters
        st.session_state["has_accident_info"] = False
        if total_crashes_max is not None:
            st.session_state["max_total_crashes"] = total_crashes_max
        if at_fault_crashes_max is not None:
            st.session_state["max_total_at_fault"] = at_fault_crashes_max
        if pct_at_fault_max is not None:
            st.session_state["max_pct_at_fault"] = pct_at_fault_max
        if safety_index_min is not None:
            st.session_state["min_safety_index"] = safety_index_min

        # Prospect readiness
        st.session_state["ready_to_contact"] = False

    # ------------------------------------------------------------------
    # Company fit score filter (applies globally)
    # ------------------------------------------------------------------
    min_fit = st.sidebar.number_input(
        "Minimum Company Fit Score",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        key="min_fit_score",
    )

    # Start with a mask that keeps all rows, then refine it with each filter
    mask = pd.Series(True, index=df.index)

    # Company fit score filter
    if "company_fit_score" in df.columns:
        mask &= df["company_fit_score"] >= float(min_fit)

    # ------------------------------------------------------------------
    # Geographic filters
    # ------------------------------------------------------------------
    with st.sidebar.expander("Geographic Filters", expanded=False):
        west_only = st.checkbox(
            "West of the Mississippi",
            value=False,
            key="west_of_mississippi",
        )

        exclude_special = st.checkbox(
            "Exclude AK, HI, NJ, NY",
            value=False,
            key="exclude_ak_hi_nj_ny",
        )

        verified_only = st.checkbox(
            "Only include verified addresses",
            value=False,
            key="verified_addresses_only",
        )

        selected_states = st.multiselect(
            "Physical State",
            options=states,
            key="phy_state_selection",
        )

    # Geographic portions of the mask
    state_msg_parts: list[str] = []

    if west_only:
        mask &= df["phy_state"].isin(west_states)
        state_msg_parts.append("West of the Mississippi only")

    if selected_states:
        mask &= df["phy_state"].isin(selected_states)
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
    # Fleet size filters (mileage, drivers, units)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Fleet Size Filters", expanded=False):
        # Recent mileage
        if mileage_col in df.columns:
            min_miles_input = st.number_input(
                "Min recent mileage",
                min_value=miles_min,
                max_value=miles_ui_max,
                value=st.session_state.get("mileage_min", miles_min),
                step=1000,
                key="mileage_min",
            )

            max_miles_input = st.number_input(
                "Max recent mileage",
                min_value=miles_min,
                max_value=miles_ui_max,
                value=st.session_state.get("mileage_max", miles_ui_max),
                step=1000,
                key="mileage_max",
            )

            low = min(min_miles_input, max_miles_input)
            high = max(min_miles_input, max_miles_input)

            s_all = get_numeric_series(df, mileage_col)
            if s_all is not None:
                mask &= s_all.between(low, high)

        # Drivers
        if drivers_col in df.columns:
            min_drivers_val = st.number_input(
                "Min drivers",
                min_value=drivers_min,
                max_value=drivers_ui_max,
                value=st.session_state.get("min_drivers", max(1, drivers_min)),
                step=1,
                key="min_drivers",
            )
            max_drivers_val = st.number_input(
                "Max drivers",
                min_value=drivers_min,
                max_value=drivers_ui_max,
                value=st.session_state.get("max_drivers", drivers_ui_max),
                step=1,
                key="max_drivers",
            )

            d_low = min(min_drivers_val, max_drivers_val)
            d_high = max(min_drivers_val, max_drivers_val)

            s_all = get_numeric_series(df, drivers_col)
            if s_all is not None:
                mask &= s_all.between(d_low, d_high)

        # Power units
        if units_col in df.columns:
            min_units_val = st.number_input(
                "Min power units",
                min_value=units_min,
                max_value=units_ui_max,
                value=st.session_state.get("min_units", max(1, units_min)),
                step=1,
                key="min_units",
            )
            max_units_val = st.number_input(
                "Max power units",
                min_value=units_min,
                max_value=units_ui_max,
                value=st.session_state.get("max_units", units_ui_max),
                step=1,
                key="max_units",
            )

            u_low = min(min_units_val, max_units_val)
            u_high = max(min_units_val, max_units_val)

            s_all = get_numeric_series(df, units_col)
            if s_all is not None:
                mask &= s_all.between(u_low, u_high)

    # ------------------------------------------------------------------
    # Operation-type filters (flag columns + carrier_operation)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Operation Type Filters", expanded=False):
        available_labels = [
            label
            for label, col in flag_label_to_col.items()
            if col in df.columns
        ]

        selected_flag_labels = st.multiselect(
            "Include companies where ANY of these flags are true:",
            options=available_labels,
            key="operation_flags",
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

        if "carrier_operation" in df.columns:
            carrier_types = sorted(df["carrier_operation"].dropna().unique())
            selected_carrier_types = st.multiselect(
                "Carrier Type",
                options=carrier_types,
                key="carrier_type_filter",
            )
            if selected_carrier_types:
                mask &= df["carrier_operation"].isin(selected_carrier_types)

    # ------------------------------------------------------------------
    # Insurance history filters
    # ------------------------------------------------------------------
    with st.sidebar.expander("Insurance History Filters", expanded=False):
        has_insurance = st.checkbox(
            "Only show companies with insurance history",
            value=False,
            key="has_insurance_info",
        )

        if filings_min is not None and filings_max is not None:
            min_filings, max_filings = st.slider(
                "Total Insurance Filings",
                min_value=filings_min,
                max_value=filings_max,
                value=(filings_min, filings_max),
                step=1,
                key="filings_range",
            )

            s_all = get_numeric_series(df, filings_col)
            if s_all is not None:
                has_val = s_all.notna()
                in_range = (s_all >= min_filings) & (s_all <= max_filings)
                mask &= (~has_val) | in_range

        if insurers_min is not None and insurers_max is not None:
            min_insurers, max_insurers = st.slider(
                "Insurance Companies Used",
                min_value=insurers_min,
                max_value=insurers_max,
                value=(insurers_min, insurers_max),
                step=1,
                key="insurers_range",
            )

            s_all = get_numeric_series(df, insurers_col)
            if s_all is not None:
                has_val = s_all.notna()
                in_range = (s_all >= min_insurers) & (s_all <= max_insurers)
                mask &= (~has_val) | in_range

        if gap_min is not None and gap_max is not None:
            min_gap = st.number_input(
                "Min median days between filings",
                value=gap_min,
                step=1,
                key="median_gap_min",
            )
            max_gap = st.number_input(
                "Max median days between filings",
                value=gap_max,
                step=1,
                key="median_gap_max",
            )

            low_gap = min(min_gap, max_gap)
            high_gap = max(min_gap, max_gap)

            s_all = get_numeric_series(df, median_gap_col)
            if s_all is not None:
                has_val = s_all.notna()
                in_range = (s_all >= low_gap) & (s_all <= high_gap)
                mask &= (~has_val) | in_range

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
        )

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
            )

            s_all = get_numeric_series(df, total_crashes_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all <= max_total_crashes)

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
            )

            s_all = get_numeric_series(df, at_fault_crashes_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all <= max_total_at_fault)

        if (
            pct_at_fault_col in df.columns
            and pct_at_fault_max is not None
            and pct_at_fault_max > 0
        ):
            max_pct_at_fault = st.slider(
                "Max % at fault",
                min_value=0.0,
                max_value=float(pct_at_fault_max),
                value=float(st.session_state.get("max_pct_at_fault", pct_at_fault_max)),
                step=0.01,
                key="max_pct_at_fault",
            )

            s_all = get_numeric_series(df, pct_at_fault_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all <= max_pct_at_fault)

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
            )

            s_all = get_numeric_series(df, safety_index_col)
            if s_all is not None:
                mask &= s_all.isna() | (s_all >= min_safety_idx)

        if has_accidents and total_crashes_col in df.columns:
            s_all = get_numeric_series(df, total_crashes_col)
            if s_all is not None:
                mask &= s_all.notna() & (s_all != 0)

    # ------------------------------------------------------------------
    # Default filters (country, mail, hazmat, territories, outlier caps)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Default Filters", expanded=False):
        territories_to_exclude = {"PR", "GU", "AS", "MP", "VI"}

        exclude_territories = st.checkbox(
            "Exclude US territories (PR, GU, AS, MP, VI)",
            key="exclude_territories",
        )

        if exclude_territories and "phy_state" in df.columns:
            mask &= ~df["phy_state"].isin(territories_to_exclude)

        if "phy_country" in df.columns and default_country is not None:
            selected_countries = st.multiselect(
                "Country",
                options=countries,
                key="phy_country_selection",
            )
            if selected_countries:
                mask &= df["phy_country"].isin(selected_countries)

        if "us_mail" in df.columns and default_mail is not None:
            mail_choice = st.selectbox(
                "US Mail",
                options=["All"] + mail_options,
                key="us_mail_filter",
            )
            if mail_choice != "All":
                mask &= df["us_mail"] == mail_choice

        if "hm_flag" in df.columns and default_hm is not None:
            hm_choice = st.selectbox(
                "Hazardous Material",
                options=["All"] + hm_options,
                key="hm_flag_filter",
            )
            if hm_choice == "N":
                mask &= df["hm_flag"] == "N"
            elif hm_choice == "Y":
                mask &= df["hm_flag"] == "Y"

        if miles_outlier_cap is not None and mileage_col in df.columns:
            cap_miles = st.checkbox(
                "Exclude extreme mileage outliers (top 1%)",
                key="cap_mileage_outliers",
            )
            if cap_miles:
                s_all = get_numeric_series(df, mileage_col)
                if s_all is not None:
                    mask &= s_all.isna() | (s_all <= miles_outlier_cap)

        if drivers_outlier_cap is not None and drivers_col in df.columns:
            cap_drivers = st.checkbox(
                "Exclude extreme driver count outliers (top 1%)",
                key="cap_driver_outliers",
            )
            if cap_drivers:
                s_all = get_numeric_series(df, drivers_col)
                if s_all is not None:
                    mask &= s_all.isna() | (s_all <= drivers_outlier_cap)

        if units_outlier_cap is not None and units_col in df.columns:
            cap_units = st.checkbox(
                "Exclude extreme power unit outliers (top 1%)",
                key="cap_unit_outliers",
            )
            if cap_units:
                s_all = get_numeric_series(df, units_col)
                if s_all is not None:
                    mask &= s_all.isna() | (s_all <= units_outlier_cap)

    # ------------------------------------------------------------------
    # Prospect readiness filters (contactability)
    # ------------------------------------------------------------------
    with st.sidebar.expander("Prospect Readiness Filters", expanded=False):
        ready_only = st.checkbox(
            "Only show companies that have email or phone",
            key="ready_to_contact",
        )

    if ready_only:
        email_exists = (
            df["email_address"].notna()
            & (df["email_address"].astype(str).str.strip() != "")
        ) if "email_address" in df.columns else pd.Series(False, index=df.index)

        phone_exists = (
            df["telephone"].notna()
            & (df["telephone"].astype(str).str.strip() != "")
        ) if "telephone" in df.columns else pd.Series(False, index=df.index)

        mask &= email_exists | phone_exists

    # ------------------------------------------------------------------
    # Apply the combined mask once to create filtered_df
    # ------------------------------------------------------------------
    filtered_df = df[mask]
else:
    # If phy_state is missing, downstream sections will rely directly on df
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
# Choropleth + metric-selectable Top 10 bar chart
# ----------------------------------------------------------------------
if "phy_state" in df.columns:
    col_map, col_map_right = st.columns([1, 1])

    # The map uses the current filtered set so it stays in sync with filters
    source_for_map = filtered_df

    # Aggregate metrics by state
    agg_dict = {"CompanyCount": ("phy_state", "size")}

    if "recent_mileage" in source_for_map.columns:
        agg_dict["avg_recent_mileage"] = ("recent_mileage", "mean")
    if "driver_total" in source_for_map.columns:
        agg_dict["avg_drivers"] = ("driver_total", "mean")
    if "nbr_power_unit" in source_for_map.columns:
        agg_dict["avg_power_units"] = ("nbr_power_unit", "mean")
    if "num_filings" in source_for_map.columns:
        agg_dict["InsuranceCount"] = ("num_filings", lambda s: s.notna().sum())

    if len(source_for_map) > 0:
        state_agg = (
            source_for_map.groupby("phy_state")
            .agg(**agg_dict)
            .reset_index()
            .rename(columns={"phy_state": "State"})
        )
    else:
        state_agg = pd.DataFrame(columns=["State", "CompanyCount"])

    if "CompanyCount" in state_agg.columns and "InsuranceCount" in state_agg.columns:
        state_agg["InsurancePct"] = np.where(
            state_agg["CompanyCount"] > 0,
            state_agg["InsuranceCount"] / state_agg["CompanyCount"] * 100.0,
            np.nan,
        )

    metric_options = {
        "Company Count": ("CompanyCount", "Companies"),
    }
    if "avg_recent_mileage" in state_agg.columns:
        metric_options["Avg Recent Mileage"] = ("avg_recent_mileage", "Avg Recent Mileage")
    if "avg_drivers" in state_agg.columns:
        metric_options["Avg Drivers"] = ("avg_drivers", "Avg Drivers")
    if "avg_power_units" in state_agg.columns:
        metric_options["Avg Power Units"] = ("avg_power_units", "Avg Power Units")
    if "InsuranceCount" in state_agg.columns:
        metric_options["Companies with Insurance History"] = (
            "InsuranceCount",
            "Companies with Insurance History",
        )
    if "InsurancePct" in state_agg.columns:
        metric_options["Percent with Insurance History"] = (
            "InsurancePct",
            "% with Insurance History",
        )

    with col_map:
        st.subheader("Nationwide Metrics")
        selected_metric_label = st.selectbox(
            "Choropleth Metric",
            options=list(metric_options.keys()),
            index=0,
        )
        metric_col, metric_title = metric_options[selected_metric_label]

        if not state_agg.empty:
            fig = px.choropleth(
                state_agg,
                locations="State",
                locationmode="USA-states",
                color=metric_col,
                color_continuous_scale="Blues",
                scope="usa",
                labels={metric_col: metric_title},
            )

            if metric_col in ["CompanyCount", "InsuranceCount"]:
                hover_template = (
                    "<b>%{location}</b><br>"
                    f"{metric_title}: " + "%{z:,.0f}<extra></extra>"
                )
                tickfmt = ",d"
            else:
                hover_template = (
                    "<b>%{location}</b><br>"
                    f"{metric_title}: " + "%{z:,.2f}<extra></extra>"
                )
                tickfmt = ",.2f"

            fig.update_traces(hovertemplate=hover_template)
            fig.update_coloraxes(colorbar_tickformat=tickfmt)

            fig.update_layout(
                height=420,
                margin=dict(l=0, r=0, t=10, b=0),
                coloraxis_colorbar=dict(
                    xanchor="left",
                    x=1.01,
                    y=0.5,
                    len=0.8,
                    thickness=12,
                    title=metric_title,
                ),
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No state data available for current filters.")

    with col_map_right:
        unique_states = source_for_map["phy_state"].dropna().unique()

        # Case 1: exactly one state -> county-level view
        if len(unique_states) == 1 and "county_fips" in source_for_map.columns:
            state_abbr = unique_states[0]
            state_fips = STATE_ABBR_TO_FIPS.get(state_abbr)

            st.subheader(f"County Metrics – {state_abbr}")
            st.markdown("<div style='height:90px'></div>", unsafe_allow_html=True)

            if not state_fips:
                st.info("No FIPS mapping available for this state.")
            else:
                state_df = source_for_map[
                    (source_for_map["phy_state"] == state_abbr)
                    & (source_for_map["county_fips"].notna())
                ]

                base_counties = get_state_county_lookup(state_fips)
                if base_counties.empty:
                    st.info("No county shapes found for this state.")
                else:
                    county_counts = base_counties.copy()

                    metric_series = None

                    if not state_df.empty:
                        if metric_col == "CompanyCount":
                            metric_series = (
                                state_df.groupby("county_fips")["county_fips"]
                                .size()
                                .rename("MetricValue")
                            )
                        elif metric_col == "avg_recent_mileage" and "recent_mileage" in state_df.columns:
                            metric_series = (
                                state_df.groupby("county_fips")["recent_mileage"]
                                .mean()
                                .rename("MetricValue")
                            )
                        elif metric_col == "avg_drivers" and "driver_total" in state_df.columns:
                            metric_series = (
                                state_df.groupby("county_fips")["driver_total"]
                                .mean()
                                .rename("MetricValue")
                            )
                        elif metric_col == "avg_power_units" and "nbr_power_unit" in state_df.columns:
                            metric_series = (
                                state_df.groupby("county_fips")["nbr_power_unit"]
                                .mean()
                                .rename("MetricValue")
                            )
                        elif metric_col == "InsuranceCount" and "num_filings" in state_df.columns:
                            metric_series = (
                                state_df.groupby("county_fips")["num_filings"]
                                .apply(lambda s: s.notna().sum())
                                .rename("MetricValue")
                            )
                        elif metric_col == "InsurancePct" and "num_filings" in state_df.columns:
                            by_county = state_df.groupby("county_fips")
                            counts = by_county["county_fips"].size()
                            ins_counts = by_county["num_filings"].apply(lambda s: s.notna().sum())
                            pct = np.where(counts > 0, ins_counts / counts * 100.0, np.nan)
                            metric_series = pd.Series(pct, index=counts.index, name="MetricValue")

                    if metric_series is not None:
                        metric_df = (
                            metric_series.reset_index()
                            .rename(columns={"county_fips": "county_fips"})
                        )
                        county_counts = county_counts.merge(
                            metric_df,
                            on="county_fips",
                            how="left",
                        )
                        county_counts["MetricValue"] = county_counts["MetricValue"].fillna(0.0)
                    else:
                        county_counts["MetricValue"] = 0.0

                    counties_geojson = load_state_counties_geojson(state_fips)

                    fig_counties = px.choropleth(
                        county_counts,
                        geojson=counties_geojson,
                        locations="county_fips",
                        color="MetricValue",
                        featureidkey="properties.GEOID",
                        color_continuous_scale="Blues",
                        labels={"MetricValue": metric_title},
                    )

                    fig_counties.update_geos(
                        fitbounds="locations",
                        visible=False,
                    )

                    fig_counties.update_traces(
                        customdata=county_counts[["county_name"]].to_numpy()
                    )

                    if metric_col in ["CompanyCount", "InsuranceCount"]:
                        county_hover = (
                            "%{customdata[0]}<br>"
                            f"{metric_title}: " + "%{z:,.0f}<extra></extra>"
                        )
                        tickfmt_counties = ",d"
                    else:
                        county_hover = (
                            "%{customdata[0]}<br>"
                            f"{metric_title}: " + "%{z:,.2f}<extra></extra>"
                        )
                        tickfmt_counties = ",.2f"

                    fig_counties.update_traces(hovertemplate=county_hover)
                    fig_counties.update_coloraxes(colorbar_tickformat=tickfmt_counties)

                    fig_counties.update_layout(
                        height=420,
                        margin=dict(l=0, r=0, t=10, b=0),
                        coloraxis_colorbar=dict(
                            xanchor="left",
                            x=1.01,
                            y=0.5,
                            len=0.8,
                            thickness=12,
                        ),
                    )

                    st.plotly_chart(fig_counties, use_container_width=True)

        # Case 2: zero or multiple states -> Top 10 bar chart by metric
        else:
            if not state_agg.empty:
                st.subheader("Top States")

                top10 = state_agg.sort_values(metric_col, ascending=False).head(10)

                vmin = state_agg[metric_col].min()
                vmax = state_agg[metric_col].max()
                colorscale = px.colors.sequential.Blues

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
# Fleet metrics & fit score distribution
# ----------------------------------------------------------------------
st.subheader("Fleet Metrics & Fit Score Distribution")

col_hist, col_units, col_drivers, col_miles = st.columns(4)

# --------- Fit score histogram -----------
with col_hist:
    if "company_fit_score" in filtered_df.columns:
        fig_fit_hist = px.histogram(
            filtered_df,
            x="company_fit_score",
            labels={"company_fit_score": "Company Fit Score"},
            title="Fit Scores",
        )

        fig_fit_hist.update_traces(
            xbins=dict(
                start=0.0,
                end=1.0,
                size=0.05,
            ),
            marker_line_color="black",
            marker_line_width=2.5,
        )

        trace = fig_fit_hist.data[0]
        bin_start = float(trace.xbins.start)
        bin_end = float(trace.xbins.end)
        bin_size = float(trace.xbins.size)

        n_bins = int(round((bin_end - bin_start) / bin_size))
        starts = bin_start + bin_size * np.arange(n_bins)
        ends = starts + bin_size

        fig_fit_hist.update_traces(
            customdata=np.stack([starts, ends], axis=-1),
            hovertemplate=(
                "Range: %{customdata[0]:.2f}–%{customdata[1]:.2f}<br>"
                "Count: %{y:,.0f}<extra></extra>"
            ),
        )

        median_fit = float(filtered_df["company_fit_score"].median())
        fig_fit_hist.add_vline(x=median_fit, line_dash="dash")

        fig_fit_hist.update_xaxes(range=[0, 1])
        fig_fit_hist.update_yaxes(title_text="Count", tickformat=",d")
        fig_fit_hist.update_layout(height=300)

        st.plotly_chart(fig_fit_hist, use_container_width=True)


# --------- Helper: plot metric as a line over its histogram counts ----------
def plot_metric_line_from_counts(df_in, col, label, title, container, exclude_zero=False):
    """
    Build a simple line chart showing how many companies fall into each
    bin of a numeric metric. This gives a sense of distribution shape
    without exposing individual records.

    Args:
        df_in:      DataFrame to use (typically filtered_df).
        col:        Column name to plot.
        label:      X-axis label for the metric.
        title:      Chart title.
        container:  Streamlit layout container to render into.
        exclude_zero: If True, rows with value 0 are removed before
                      computing the histogram.
    """
    if col not in df_in.columns:
        return

    s = pd.to_numeric(df_in[col], errors="coerce").dropna()
    if exclude_zero:
        s = s[s != 0]

    if s.empty:
        return

    counts, bin_edges = np.histogram(s, bins=20)
    centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    temp = pd.DataFrame({label: centers, "Count": counts})

    fig_line = px.line(
        temp,
        x=label,
        y="Count",
        title=title,
        labels={label: label, "Count": "Count"},
    )

    fig_line.update_traces(
        hovertemplate=(
            f"{label}: "
            "%{x:,.0f}<br>"
            "Count: %{y:,.0f}<extra></extra>"
        )
    )

    fig_line.update_yaxes(tickformat=",d")
    fig_line.update_xaxes(tickformat=",d")
    fig_line.update_layout(height=300)

    with container:
        st.plotly_chart(fig_line, use_container_width=True)


# --------- Power units distribution ----------
plot_metric_line_from_counts(
    filtered_df,
    col="nbr_power_unit",
    label="Power Units",
    title="Power Units Distribution",
    container=col_units,
)

# --------- Drivers distribution ----------
plot_metric_line_from_counts(
    filtered_df,
    col="driver_total",
    label="Drivers",
    title="Drivers Distribution",
    container=col_drivers,
)

# --------- Recent mileage distribution (exclude zero mileage) ----------
plot_metric_line_from_counts(
    filtered_df,
    col="recent_mileage",
    label="Mileage",
    title="Recent Mileage Distribution",
    container=col_miles,
    exclude_zero=True,
)

# ----------------------------------------------------------------------
# Company list + download
# ----------------------------------------------------------------------
full_rename = {
    "dot_number": "DOT Number",
    "legal_name": "Company Legal Name",
    "company_fit_score": "Company Fit Score",
    "email_address": "Email Address",
    "telephone": "Phone Number",
    "phy_state": "Physical State",
    "dba_name": "Doing Business As Name",
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
    "safety_index": "Safety Index",
    "match_status": "Address Match Status",
    "match_type": "Match Type",
    "lat": "Latitude",
    "lon": "Longitude",
    "county_fips": "County FIPS",
    "county_name": "County Name",
    "county_statefp": "State FIPS",
}

base_display_cols = [
    "dot_number",
    "company_fit_score",
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
    "recent_mileage",
    "nbr_power_unit",
    "driver_total",
    "top_company",
    "median_gap_days",
    "safety_index",
    "match_status",
]

base_display_cols = [c for c in base_display_cols if c in filtered_df.columns]

display_df = filtered_df[base_display_cols].copy()

if "dot_number" in filtered_df.columns:
    fm_links = (
        "<a href='https://safer.fmcsa.dot.gov/query.asp?"
        "searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string="
        + filtered_df.loc[display_df.index, "dot_number"].astype(str)
        + "' target='_blank'>FMCSA Profile</a>"
    )

    if "company_fit_score" in display_df.columns:
        insert_pos = display_df.columns.get_loc("company_fit_score") + 1
    else:
        insert_pos = 1

    display_df.insert(insert_pos, "FMCSA Link", fm_links)

display_df = display_df.rename(columns=full_rename)

if len(filtered_df) == 0:
    st.info("No companies match the current filters, so there is nothing to download.")
else:
    max_export = len(filtered_df)
    default_export = min(500, max_export)

    col_export, _ = st.columns([1, 3])
    with col_export:
        st.markdown(
            "<div style='font-size:18px; font-weight:600; margin-bottom:4px;'>"
            "Number of top companies to download"
            "</div>",
            unsafe_allow_html=True,
        )

        export_n = st.number_input(
            label="",
            min_value=1,
            max_value=max_export,
            value=default_export,
            step=50,
            key="export_n",
        )

    # Work from the same filtered set used elsewhere, then rename at the end
    full_export_df = filtered_df.head(export_n).copy()

    if "dot_number" in full_export_df.columns:
        full_export_df["FMCSA Link"] = (
            '=HYPERLINK("https://safer.fmcsa.dot.gov/query.asp?'
            'searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string='
            + full_export_df["dot_number"].astype(str)
            + '","FMCSA Profile")'
        )

    full_export_df = full_export_df.rename(columns=full_rename)

    csv_data = full_export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=f"⬇️ Download Top {export_n} Filtered Companies (Expanded Columns) (CSV)",
        data=csv_data,
        file_name=f"drivepoints_top{export_n}_minfit{min_fit:.2f}_filtered.csv",
        mime="text/csv",
    )

st.subheader("Company List with Contact Info Preview")
st.write(
    display_df.head(50).to_html(escape=False, index=False),
    unsafe_allow_html=True
)
