# Trucking Market Research using Publicly Available Data

Ben Sullivan, Jared Donohue, Moacir P. de Sá Pereira, Jialin Wen

[Final Report (LaTeX PDF)]()

## Purpose
Deliver a market segmentation tool find which trucking companies are a good fit for [DrivePoints](https://drivepoints.com/) insurance.

## In this Repository  
1. **Data Fetching & Exploratory Data Analysis**: `data/` and `notebooks/`
2. **LLM Experiments**: `llm/`
3. **Statistical Modeling & Evaluation**: `evaluation/`
4. **Market Segmentation Dashboard (Streamlit)**: `dashboard/`

## How to Use this Repository
1. Download the latest version of the USDOT Monthly Carrier Census (see Data Sources)
2. Move the downloaded CSV file into the `data/` folder of this repository
3. Run `pip install -r requirements.txt` to download required package dependencies
4. Run `scripts/convert_to_parquet.py` to create a parquet file for the data
5. [optional] assess the data quality (DQS)
6. [optional] join auxilliary data
7. [optional] generate the stat model outputs
8. Run `streamlit run dashboard/app.py` to view and interact with the company dashboard

## Data Sources
- **USDOT Monthly Carrier Census**: This primary dataset is ~2.09M records from the USDOT Motor Carrier Census, containing registration data of all active Interstate and Intrastate Motor Carriers of property and/or passengers. The dataset contains 42 columns, including the USDOT Number, company names, addresses, contacts, telephone and fax numbers, e-mail, HazMat flag, passenger carrier flag, number of power units, number of drivers, mileage, mileage year, operation, and classification registration information. The file is comma delimited with one carrier per row. https://data.transportation.gov/Trucking-and-Motorcoaches/SMS-Input-Motor-Carrier-Census-Information/kjg3-diqy/about_data
- **USDOT Insurance History (InsHist)**: https://data.transportation.gov/Trucking-and-Motorcoaches/InsHist-All-With-History/nzpz-e5xn/about_data
- **FMCSA Safety and Fitness Electronic Records (SAFER)**: https://safer.fmcsa.dot.gov/
- **Fatality Analysis Reporting System (FARS)**: https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars
- **Data Axle**: https://www.data-axle.com/
