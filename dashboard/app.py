# TO RUN THIS DASHBOARD:
# > streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="DrivePoints Potential Customer Dashboard",
    layout="wide",
)

st.title("🚚 DrivePoints Potential Customer Dashboard")
st.markdown(
    "Preview of transportation companies, ranked, with easy access to contacts and state trends. "
    "Company Fit Score is randomly generated for prototype."
)

DATA_PATH = "../data/transportation_data_20251013_135544.parquet" # or any version of the USDOT FMCSA Census dataset.

@st.cache_data
def load_data():
    return pd.read_parquet(DATA_PATH)

df = load_data()

# Add mock fit score and re-order columns
np.random.seed(42)
df["company_fit_score"] = np.round(np.random.uniform(0.0, 1.0, size=len(df)), 3)
display_columns = ["dot_number", "legal_name", "company_fit_score", "email_address", "telephone"]
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
        title="Company Count per US State"
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
