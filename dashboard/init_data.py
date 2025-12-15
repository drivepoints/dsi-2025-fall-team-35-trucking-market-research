import os
import sys
import subprocess
import pandas as pd
import streamlit as st
from dashboard.config import PROJECT_ROOT
from dashboard.utils import (
    get_current_version,
    set_current_version,
    data_path_for_version,
)


def init_data() -> pd.DataFrame:
    """Initialize and load the dataset for the Streamlit app.

    This function checks for the current data version, attempts to load the
    corresponding dataset, and if missing, prompts the user to fetch and
    preprocess the data for a specified version.

    Returns: pd.DataFrame
    """
    version = get_current_version()

    if version is None:
        st.error("No version file found.")
        st.info("Specify a version to download/process.")
    else:
        st.caption(f"Current data version: **{version}**")

    data_path = data_path_for_version(version) if version else None

    df = None
    data_loaded = False

    if data_path and os.path.exists(data_path):
        try:
            df = pd.read_parquet(data_path)
            data_loaded = True
        except Exception as e:
            st.error(f"Failed to load dataset: {data_path}")
            st.exception(e)
    else:
        st.warning(f"Expected dataset missing: `{data_path}`")

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
                        [sys.executable, "-m", "dashboard.preprocess", input_version],
                        cwd=PROJECT_ROOT,
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

    return df
