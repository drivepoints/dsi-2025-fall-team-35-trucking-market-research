# -*- coding: utf-8 -*-

"""
Moacir P. de Sá Pereira

"""

import polars as pl
from rapidfuzz import process, fuzz
from tqdm import tqdm
import numpy as np

BUCKET_SIZE = 0.01
RADIUS = 0.001
BATCH_SIZE = 1000


df = pl.read_parquet("./data/geocoded_addresses.parquet")

daxle_df_raw = pl.scan_parquet("./data/data-axle.parquet")


def calculate_bucket(f: float) -> int:
    return int(np.floor(f / BUCKET_SIZE))


daxle_df = (
    (
        daxle_df_raw.select(
            "latitude",
            "longitude",
            match_address=pl.concat_str(
                [
                    pl.col("address_line_1"),
                    pl.col("city"),
                    pl.col("state"),
                    pl.col("zipcode"),
                ],
                separator=", ",
            ),
        )
        .with_columns(
            lat_bucket=(pl.col("latitude") / BUCKET_SIZE).floor().cast(pl.Int32),
            lon_bucket=(pl.col("longitude") / BUCKET_SIZE).floor().cast(pl.Int32),
        )
        .with_columns(
            (pl.col("lat_bucket") * 100_000 + pl.col("lon_bucket")).alias("bucket_id")
        )
    )
    .with_row_index(name="data_axle_row_index")
    .collect()
)


def neighbor_ids(lat_bucket: int, lon_bucket: int) -> list[int]:
    return [
        (lat_bucket + dlat) * 100_000 + (lon_bucket + dlon)
        for dlat in (-1, 0, 1)
        for dlon in (-1, 0, 1)
    ]


def get_candidates(lat: int, lon: int) -> pl.DataFrame:
    lat_bucket = calculate_bucket(lat)
    lon_bucket = calculate_bucket(lon)
    bucket_ids = neighbor_ids(lat_bucket, lon_bucket)

    return daxle_df.filter(pl.col("bucket_id").is_in(bucket_ids))


def match_batch(batch: pl.DataFrame):
    results = []

    for truck in tqdm(batch.iter_rows(named=True)):
        lat, lon, addr = (truck["lat"], truck["lon"], truck["matched_address"])

        if lat is None or lon is None or addr is None:
            results.append((None, 0, -1))
            continue

        candidates = get_candidates(lat, lon)

        # Radius filter
        candidates = candidates.filter(
            ((pl.col("latitude") - lat).abs() < RADIUS)
            & ((pl.col("longitude") - lon).abs() < RADIUS)
        )

        if candidates.is_empty():
            results.append((None, 0, -1))
            continue

        # Fuzzy match on addresses
        choices = candidates["match_address"].drop_nulls().to_list()
        if not choices:
            results.append((None, 0, -1))
            continue

        matches = process.extract(
            addr,
            choices,
            scorer=fuzz.token_sort_ratio,
            limit=1,
        )

        if matches:
            match, score, match_idx = matches[0]
            match_id = candidates["data_axle_row_index"][match_idx]
            results.append((match, score, match_id))
        else:
            results.append((None, 0.0, None))

    return results


# --- Run batched loop ---
all_matches = []
for i in tqdm(range(0, df.height, BATCH_SIZE)):
    batch_results = match_batch(df.slice(i, BATCH_SIZE))
    all_matches.extend(batch_results)

results_df = df.with_columns(
    [
        pl.Series("best_match", [m[0] for m in all_matches]),
        pl.Series("confidence", [m[1] for m in all_matches], dtype=pl.Float64),
        pl.Series("data_axle_row_index", [m[2] for m in all_matches]),
    ]
)

results_df.write_parquet("./data/data_axle_matched_addresses.parquet")

print("written")
