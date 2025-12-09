# Trucking Market Research Tool using Logistic Regression on Publicly Available Data

Ben Sullivan, Jared Donohue, Moacir P. de Sá Pereira, Jialin Wen

[Final Report (LaTeX PDF)]()

## In this Repository

1. Market Segmentation Dashboard Tool using Streamlit: `app.py`
2. Data Fetching & Exploratory Data Analysis: `data/`, `notebooks/`, `dqs/`
3. LLM Experiments: `llm/`
4. Statistical Modeling & Evaluation: `evaluation/`

## How to Run the Dashboard

1. Run `pip install -r requirements.txt` to download required package dependencies.
2. Download `master_file.parquet` ([Google Drive Link](https://drive.google.com/file/d/1BSIEEkaXgfTXaR7jr1GxFc8DCOe702yW/view?usp=drive_link)) into the root of this directory.
3. Run `streamlit run app.py` to view and interact with the market research dashboard tool.

## Data Sources

- **USDOT Monthly Carrier Census**: Primary dataset of ~2.09M records from the USDOT Motor Carrier Census, containing registration data of all active Interstate and Intrastate Motor Carriers of property and/or passengers. The dataset contains 42 columns, including the USDOT Number, company names, addresses, contacts, telephone and fax numbers, e-mail, HazMat flag, passenger carrier flag, number of power units, number of drivers, mileage, mileage year, operation, and classification registration information. The file is comma delimited with one carrier per row. https://data.transportation.gov/Trucking-and-Motorcoaches/SMS-Input-Motor-Carrier-Census-Information/kjg3-diqy/about_data
- **USDOT Insurance History (InsHist)**: https://data.transportation.gov/Trucking-and-Motorcoaches/InsHist-All-With-History/nzpz-e5xn/about_data
- **FMCSA Safety and Fitness Electronic Records (SAFER)**: https://safer.fmcsa.dot.gov/
- **Fatality Analysis Reporting System (FARS)**: https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars
- **Data Axle**: https://www.data-axle.com/
- **SAFER Company Snaphors by DOT number**: https://safer.fmcsa.dot.gov/CompanySnapshot.aspx
- **QCMobile API**: https://mobile.fmcsa.dot.gov/QCDevsite/docs/qcApi
