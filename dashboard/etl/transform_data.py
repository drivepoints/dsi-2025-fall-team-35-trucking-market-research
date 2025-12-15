import polars as pl


def transform_data(df: pl.DataFrame) -> pl.DataFrame:
    """Transform the DataFrame by converting date columns and correcting
    mileage data.
    Args:
        df (pl.DataFrame): Input DataFrame with raw data.

    Returns:
        pl.DataFrame: Transformed DataFrame with correct data types.
    """

    hazmat_mapping = {
        "A": "Interstate",
        "B": "Intrastate Hazmat",
        "C": "Intrastate Non-Hazmat",
    }

    return df.with_columns(
        # Convert date columns from string to Date type
        pl.col("add_date")
        .cast(pl.String)
        .str.strptime(pl.Date, "%d-%b-%y")
        .alias("add_date"),
        pl.col("mcs150_date")
        .cast(pl.String)
        .str.strptime(pl.Date, "%d-%b-%y")
        .alias("mcs150_date"),
        # Correct recent mileage data to use nulls instead of zeros
        pl.when(pl.col("recent_mileage_year") == 0)
        .then(pl.lit(None))
        .otherwise(pl.col("recent_mileage_year"))
        .alias("recent_mileage_year"),
        pl.when(pl.col("recent_mileage") == 0)
        .then(pl.lit(None))
        .otherwise(pl.col("recent_mileage"))
        .alias("recent_mileage"),
        # Ensure that dot_number is treated as String
        pl.col("dot_number").cast(pl.String).alias("dot_number"),
        # Map 'carrier_operation' codes to descriptive text
        pl.col("carrier_operation").replace(hazmat_mapping).alias("carrier_operation"),
    )
