# -*- coding: utf-8 -*-

"""
Moacir P. de Sá Pereira

This file takes the parquet file with the full dataset. It then extracts
the address fields and chunks the data into 1000-record size chunks and
saves them as intermediate csvs that are uploaded to the Census geocoder.

The results from the census are all written to an intermittent (large) file
for further processing. This is all done to avoid having to hit the Census
geocoder every time, as it takes about 4 hours to iterate through all the
data.
"""

import polars as pl
import math
import requests
from tqdm import tqdm
import time

df = pl.read_parquet(
    "./data/SMS_Input_-_Motor_Carrier_Census_Information_20250919.parquet"
)

addresses_df = df.select(
    pl.col("DOT_NUMBER"),
    pl.col("PHY_STREET"),
    pl.col("PHY_CITY"),
    pl.col("PHY_STATE"),
    pl.col("PHY_ZIP"),
)


def census_batch_geocode(df: pl.DataFrame, chunk_size: int = 1000) -> pl.DataFrame:
    n = df.height
    chunks_n = math.ceil(n / chunk_size)
    results = []

    for i in tqdm(range(chunks_n)):
        df_chunk = df.slice(i * chunk_size, chunk_size)

        batch_file = f"./tmp/addresses_{i}.csv"
        df_chunk.write_csv(batch_file, include_header=False)

        url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
        with open(batch_file, "rb") as f:
            files = {"addressFile": f}
            params = {"benchmark": "Public_AR_Current"}
            response = requests.post(url, files=files, params=params)

            results.extend(response.text.splitlines())

        if i < chunks_n - 1:
            time.sleep(1)

    return results


results = census_batch_geocode(addresses_df)

raw_csv = "\n".join(results)
with open("./data/geocode_results_raw.txt", "w") as f:
    f.write(raw_csv)

print("Raw geocoded results written.")
results[0]
