import sys
import tempfile
import os
import polars as pl
import requests


def preprocess(version):
    print(f"Building dataset version {version}...")
    out_path = f"../data/sms_census_data_version_{version}.parquet"
    url = f"https://data.transportation.gov/api/archival.csv?id=kjg3-diqy&version={version}&method=export"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        csv_path = tmp.name
        print(f"Downloading CSV to temporary file: {csv_path}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)

    print("Reading CSV into DataFrame...")
    df = pl.read_csv(csv_path, infer_schema_length=100000)

    print(f"Saving to Parquet: {out_path}")
    df.write_parquet(out_path)

    os.remove(csv_path)
    print(f"Deleted temporary CSV: {csv_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: preprocess.py <version>")
        sys.exit(1)

    preprocess(sys.argv[1])
