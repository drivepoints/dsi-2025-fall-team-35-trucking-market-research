import tempfile
import os
import polars as pl
import requests
from dashboard.utils import data_path_for_version


def import_census_data(version) -> pl.DataFrame:
    """
    Docstring
    """
    print(f"Building dataset version {version}...")
    out_path = data_path_for_version(version)
    url = f"https://data.transportation.gov/api/archival.csv?id=kjg3-diqy&version={version}&method=export"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        csv_path = tmp.name
        print(f"Downloading CSV to temporary file: {csv_path}")
        response = requests.get(url, stream=True, timeout=10000)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)

    print("Reading CSV into DataFrame...")
    df = pl.read_csv(csv_path, infer_schema_length=100000)

    print(f"Saving to Parquet: {out_path}")
    df.write_parquet(out_path)

    os.remove(csv_path)
    print(f"Deleted temporary CSV: {csv_path}")

    return df
