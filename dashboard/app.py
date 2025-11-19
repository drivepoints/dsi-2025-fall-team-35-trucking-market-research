# TO RUN THIS DASHBOARD:
# > streamlit run app.py

import subprocess
import os
import sys
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from utils.data_utils import (
    get_current_version,
    set_current_version,
    data_path_for_version,
)

PREPROCESS_SCRIPT = "../scripts/preprocess.py"

st.set_page_config(
    page_title="DrivePoints Potential Customer Dashboard",
    layout="wide",
)

st.title("🚚 DrivePoints Potential Customer Dashboard")
st.markdown(
    "Preview of transportation companies, ranked, with easy access to contacts and state trends. "
    "Company Fit Score is randomly generated for prototype."
)


@st.cache_data
def load_data(path):
    return pd.read_parquet(path)


version = get_current_version()

if version is None:
    st.error("No version file found.")
    st.info("Specify a version to download/process.")
else:
    st.caption(f"Current data version: **{version}**")

expected_path = data_path_for_version(version) if version else None

df = None
data_loaded = False

if expected_path and os.path.exists(expected_path):
    try:
        df = load_data(expected_path)
        data_loaded = True
    except Exception as e:
        st.error(f"Failed to load dataset: {expected_path}")
        st.exception(e)
else:
    st.warning(f"Expected dataset missing: `{expected_path}`")


if not data_loaded:
    st.warning("Dataset Missing. Build or Fetch a Version")

    input_version = st.text_input(
        "Enter dataset version to generate (version 109 released Nov 2025):",
        value=version or "",
        placeholder="109",
    )

    if st.button("Fetch and Preprocess Data"):
        if not input_version.strip().isdigit():
            st.error("Version must be a number.")
            st.stop()

        with st.spinner(f"Running preprocess for version {input_version}..."):
            try:
                result = subprocess.run(
                    [sys.executable, PREPROCESS_SCRIPT, input_version],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                set_current_version(input_version)

                st.success(f"Preprocess complete for version {input_version}")
                st.code(result.stdout or "(no output)")
                st.rerun()

            except subprocess.CalledProcessError as e:
                st.error("Preprocessing failed.")
                st.code(e.stderr or "(no stderr)")
                st.stop()

    st.stop()

st.success(f"Dataset loaded (version {version})")

# Add mock fit score and re-order columns
np.random.seed(42)
df["company_fit_score"] = np.round(np.random.uniform(0.0, 1.0, size=len(df)), 3)
display_columns = [
    "dot_number",
    "legal_name",
    "company_fit_score",
    "email_address",
    "telephone",
]
rest = [c for c in df.columns if c not in display_columns]
df = df[display_columns + rest]

# Sort by company_fit_score descending
df.sort_values("company_fit_score", ascending=False, inplace=True)

st.subheader("Company List with Contact Info")
st.dataframe(df.head(100), use_container_width=True)

if "phy_state" in df.columns:
    st.subheader("Companies by State (Choropleth)")
    state_counts = df["phy_state"].value_counts().reset_index()
    state_counts.columns = ["State", "CompanyCount"]
    fig = px.choropleth(
        state_counts,
        locations="State",
        locationmode="USA-states",
        color="CompanyCount",
        color_continuous_scale="Blues",
        scope="usa",
        labels={"CompanyCount": "Companies"},
        title="Company Count per US State",
    )
    st.plotly_chart(fig, use_container_width=True)

if "phy_state" in df.columns:
    st.sidebar.header("Filter")
    states = ["All"] + sorted(df["phy_state"].dropna().unique())
    selected_state = st.sidebar.selectbox("Physical State", states)
    if selected_state != "All":
        filtered_df = df[df["phy_state"] == selected_state]
        st.write(f"Displaying {len(filtered_df)} rows for state: {selected_state}")
        st.dataframe(filtered_df.head(100), use_container_width=True)
