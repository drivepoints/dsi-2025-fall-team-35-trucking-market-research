import polars as pl


def transform_data(data_path):
    df = pl.read_parquet(data_path)

    return df
