# Trucking Market Research Tool using Logistic Regression on Publicly Available Data

Ben Sullivan, Jared Donohue, Moacir P. de Sá Pereira, Jialin Wen

[Final Report (LaTeX PDF)]()

## In this Repository

1. Market Segmentation Dashboard Tool using Streamlit: `app.py`
2. Data Fetching & Exploratory Data Analysis: `data/`, `notebooks/`, `dqs/`
3. LLM Experiments: `llm/`
4. Statistical Modeling & Evaluation: `evaluation/`

## How to Run the Dashboard

1. Download `master_file.parquet` ([Google Drive Link](https://drive.google.com/file/d/1BSIEEkaXgfTXaR7jr1GxFc8DCOe702yW/view?usp=drive_link)) into the root of this directory.
2. Execute the shell script:

```bash
bash run.sh
```

This will create a virtual environment using [uv](https://docs.astral.sh/uv/) if available, otherwise generic Python `venv`. It will install the requirements indicated in `requirements.txt` into the environment and then run the [Streamlit](https://streamlit.io/) dashboard app.

## Data Sources

- **USDOT Monthly Carrier Census**: Primary dataset of ~2.09M records from the USDOT Motor Carrier Census, containing registration data of all active Interstate and Intrastate Motor Carriers of property and/or passengers. The dataset contains 42 columns, including the USDOT Number, company names, addresses, contacts, telephone and fax numbers, e-mail, HazMat flag, passenger carrier flag, number of power units, number of drivers, mileage, mileage year, operation, and classification registration information. The file is comma delimited with one carrier per row. https://data.transportation.gov/Trucking-and-Motorcoaches/SMS-Input-Motor-Carrier-Census-Information/kjg3-diqy/about_data
- **USDOT Insurance History (InsHist)**: https://data.transportation.gov/Trucking-and-Motorcoaches/InsHist-All-With-History/nzpz-e5xn/about_data
- **FMCSA Safety and Fitness Electronic Records (SAFER)**: https://safer.fmcsa.dot.gov/
- **Fatality Analysis Reporting System (FARS)**: https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars
- **Data Axle**: https://www.data-axle.com/
- **SAFER Company Snaphors by DOT number**: https://safer.fmcsa.dot.gov/CompanySnapshot.aspx
- **QCMobile API**: https://mobile.fmcsa.dot.gov/QCDevsite/docs/qcApi

## ETL Pipeline:

master_file.parquet depends on:

- original census data
- Latest_company_fit_scores.csv
- geocoded_addresses.parquet
- cargo_with_categories.parquet
- insurance_summary.parquet, which is generated in Insurance Data Cleaning and relies on:
  - Some file.
- fars_crss_census.parquet, which is generated in FARS CRSS Combiner and relies on:
  - Some file.
- dqs_output.csv

…/trucks ➜ : eza -T
analysis
├── evaluation
│ ├── comparison*output.csv
│ ├── ground_truth_494.csv
│ ├── ground_truth_503.csv
│ ├── ground_truth_506.csv
│ ├── ground_truth_1000.csv
│ ├── ground_truth_1000_with_binary.csv
│ ├── log_reg_baseline.csv
│ ├── sample-for-annotation-100.csv
│ ├── sample-for-annotation-400.csv
│ └── sample_for_annotation_100_enriched.csv
├── llm
│ ├── prompts
│ │ ├── categorize_cargo_carried.py
│ │ ├── overall_fit_cot_examples_v1.py
│ │ ├── overall_fit_cot_v1.py
│ │ ├── validity_baseline_v1.py
│ │ ├── validity_cot_examples_v1.py
│ │ ├── validity_rubric_v1.py
│ │ ├── zsolt_rules_v1.py
│ │ ├── zsolt_rules_v2.py
│ │ ├── zsolt_rules_v3.py
│ │ └── zsolt_rules_v4.py
│ └── validation
│ ├── accuracy-summary.csv
│ ├── ground-truth-100.csv
│ ├── ground-truth-zsolt.csv
│ ├── initial_company_fit_accuracy.txt
│ ├── pro_binary_accuracy.txt
│ ├── sample-for-annotation-100.csv
│ └── v2_binary_accuracy.txt
├── notebooks
│ ├── crss_fault_cleaned.ipynb
│ ├── data-axle-shape.ipynb
│ ├── dqs_notebook.ipynb
│ ├── driver-ratio.svg
│ ├── fars_fault_cleaned.ipynb
│ ├── 'FARS CRSS Combiner.ipynb'
│ ├── historical-analysis.ipynb
│ ├── industry-sectorization.ipynb
│ ├── 'Insurance Data Cleaning.ipynb'
│ ├── join_with_data_axle.ipynb
│ ├── LR_1000_with_cargo_pred.ipynb
│ ├── LR_1000_with_cargo_train.ipynb
│ ├── map-geocoded-addresses.ipynb
│ ├── master_data_merge.ipynb
│ ├── mileage-ratio.png
│ ├── mileage-ratio.svg
│ ├── ndriver-ratio.png
│ ├── november-census-analysis.ipynb
│ ├── november_histograms.png
│ ├── numeric_boxplots.png
│ ├── october-census-analysis.ipynb
│ ├── 'Predicting NAICS.ipynb'
│ └── TAM_model.ipynb
└── scripts
├── add_binary_label.py
├── address_lookup.py
├── calculate_dqs.py
├── census_geocode_raw.py
├── check_previous_labels.py
├── compare_llm_to_ground_truth.py
├── compare_to_ground_truth.py
├── convert_raw_geocode_to_parquet.py
├── create_ground_truth.py
├── email_domain_validator.py
├── fetch_cargo_carried.py
├── gemini_llm_company_fit.py
├── gemini_llm_validity.py
├── match_addresses_with_data_axle.py
├── merge_cargo_carried.py
├── merge_ground_truth_files.py
├── openai_llm_validity.py
├── preprocess.py
├── sample_from_census.py
└── scrape_safer_company_snapshot_data.py
app.py
dashboard
└── app.py
data
├── current_census_data_version.txt
├── data_axle_matched_addresses
├── data_axle_matched_addresses.parquet
├── filtered_data_axle_records_with_dot.parquet
├── fully_joined_census_and_data_axle.parquet
├── geocode_results_raw.txt
├── geocoded_addresses.parquet
├── geodata
│ ├── cb_2024_us_all_500k
│ │ ├── cb_2024_02_anrc_500k.zip
│ │ ├── cb_2024_50_sdadm_500k.zip
│ │ ├── cb_2024_72_subbarrio_500k.zip
│ │ ├── cb_2024_78_estate_500k.zip
│ │ ├── cb_2024_us_aiannh_500k.zip
│ │ ├── cb_2024_us_aitsn_500k.zip
│ │ ├── cb_2024_us_bg_500k.zip
│ │ ├── cb_2024_us_cbsa_500k.zip
│ │ ├── cb_2024_us_cd119_500k.zip
│ │ ├── cb_2024_us_concity_500k.zip
│ │ ├── cb_2024_us_county_500k.zip
│ │ ├── cb_2024_us_county_within_cd119_500k.zip
│ │ ├── cb_2024_us_cousub_500k.zip
│ │ ├── cb_2024_us_csa_500k.zip
│ │ ├── cb_2024_us_division_500k.zip
│ │ ├── cb_2024_us_elsd_500k.zip
│ │ ├── cb_2024_us_metdiv_500k.zip
│ │ ├── cb_2024_us_place_500k.zip
│ │ ├── cb_2024_us_region_500k.zip
│ │ ├── cb_2024_us_scsd_500k.zip
│ │ ├── cb_2024_us_sldl_500k.zip
│ │ ├── cb_2024_us_sldu_500k.zip
│ │ ├── cb_2024_us_state_500k.zip
│ │ ├── cb_2024_us_tbg_500k.zip
│ │ ├── cb_2024_us_tract_500k.zip
│ │ ├── cb_2024_us_ttract_500k.zip
│ │ └── cb_2024_us_unsd_500k.zip
│ ├── DECENNIALDHC2020.P1-Data.csv
│ ├── tl_2020_us_zcta520
│ │ ├── tl_2020_us_zcta520.cpg
│ │ ├── tl_2020_us_zcta520.dbf
│ │ ├── tl_2020_us_zcta520.prj
│ │ ├── tl_2020_us_zcta520.shp
│ │ ├── tl_2020_us_zcta520.shp.ea.iso.xml
│ │ ├── tl_2020_us_zcta520.shp.iso.xml
│ │ └── tl_2020_us_zcta520.shx
│ └── tl_2020_us_zcta520.zip
├── historical
├── sms_census_data_version_109.parquet
└── SMS_Input*-\_Motor_Carrier_Census_Information_20250919.parquet
poetry.lock
pyproject.toml
README.md
requirements.txt
tmp
utils
├── **pycache**
│ └── data_utils.cpython-313.pyc
└── data_utils.py
