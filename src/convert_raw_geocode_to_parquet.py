# -*- coding: utf-8 -*-

"""
Moacir P. de Sá Pereira

This file takes the intermittent raw results file from the Census geocoder
and converts it into a dataframe. This is a slightly complex process
because the results we receive from the census are not predictable. If an
address does not match, we get three "cells" back, the id, the address, and
"not found," for example.



"""

import csv
import polars as pl
from tqdm import tqdm

with open("./data/geocode_results_raw.txt", "r") as f:
    results = f.read().splitlines()

# results = results[:100]

rows = []
for line in tqdm(results):
    parsed = next(csv.reader([line]))

    while len(parsed) < 8:
        parsed.append(None)

    rows.append(parsed)


expected_cols = [
    "id",
    "input_address",
    "match_status",
    "match_type",
    "matched_address",
    "lonlat",
    "tiger_line_id",
    "side",
]

rdf = pl.DataFrame(rows, schema=expected_cols, orient="row")

rdf = (
    rdf.with_columns(
        # pl.col("id").cast(pl.Int64),
        # pl.col("tiger_line_id").cast(pl.Int64),
        pl.col("match_status").cast(pl.Categorical),
        pl.col("match_type").cast(pl.Categorical),
        pl.col("side").cast(pl.Categorical),
        pl.col("lonlat").str.split(",").alias("coords"),
    )
    .with_columns(
        pl.col("coords").list.get(1).cast(pl.Float64).alias("lat"),
        pl.col("coords").list.get(0).cast(pl.Float64).alias("lon"),
    )
    .drop(["lonlat", "coords"])
)

print(rdf.glimpse())

rdf.write_parquet("./data/geocoded_addresses.parquet")


# cleaned_df.write_parquet(f"/content/drive{path_wrinkle}/Capstone Trucking
# 🚚/Data/geocode_results_cleaned.parquet")
#
# cleaned_df["match_type"].value_counts(normalize=True)
#

print(rdf["match_type"].value_counts(normalize=True))
