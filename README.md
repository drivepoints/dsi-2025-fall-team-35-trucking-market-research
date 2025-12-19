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

## ETL and Preprocessing

In its current iteration, the data application relies on `master_file.parquet`, which has been generated once for the purposes of this project.

- [`master_file.parquet`](https://drive.google.com/file/d/1BSIEEkaXgfTXaR7jr1GxFc8DCOe702yW/view?usp=sharing) is created in `analysis/notebooks/master_data_merge.ipynb`.
- `analysis/notebooks/master_data_merge.ipynb` relies on:
  - The original census data (`SMS_Input_-_Motor_Carrier_Census_Information_20250919.csv`)
  - [`Latest_company_fit_scores.csv`](https://drive.google.com/file/d/14L3jFsL5qEPSQFVecrf4fwu3rRnVw2MK/view?usp=sharing), which is produced by:
  - [`geocoded_addresses.parquet`](https://drive.google.com/file/d/1qNJuClVmmwTHQSeUDIazD_rhNh-7ovKQ/view?usp=sharing), which is produced by:
  - [`cargo_with_categories.parquet`](https://drive.google.com/file/d/1yn0ECWxu_BqdFbNkSAbMwyfKI2Chvl9D/view?usp=sharing), which is produced by:
  - `data/insurance_summary.parquet`, which is produced by:
  - `data/fars_crss_census.parquet`, which is produced by:
  - [`dqs_output.csv`](https://drive.google.com/file/d/188g4XhWKIGr86AQCQXbjqUei9J9nWpFU/view?usp=sharing), which is produced by:
