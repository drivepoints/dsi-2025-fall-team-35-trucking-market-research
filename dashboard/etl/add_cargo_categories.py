import polars as pl
from dashboard.config import CARGO_CATEGORIZED_FILE


def add_cargo_categories(df: pl.DataFrame) -> pl.DataFrame:
    """
    Adds cargo categories to the DataFrame based on the 'cargo_description' column.

    Parameters:
    df (pl.DataFrame): Input DataFrame.

    Returns:
    pl.DataFrame: DataFrame with an additional 'cargo_categorized' column.
    """
    cargo_df = pl.read_parquet(CARGO_CATEGORIZED_FILE).with_columns(
        pl.col("dot_number").cast(pl.String).alias("dot_number"),
    )

    return df.join(
        cargo_df,
        on="dot_number",
        how="left",
    )
