import pandas as pd

from indicators.indicator_pipeline import IndicatorPipeline


def test_indicator_pipeline():

    df = pd.read_parquet(
        "data/prices/RELIANCE.parquet"
    )

    pipeline = IndicatorPipeline()

    df = pipeline.execute(df)

    expected_columns = [
        "return_3m",
        "return_6m",
        "return_9m",
        "volatility_3m",
        "momentum_score",
    ]

    for column in expected_columns:

        assert column in df.columns

    latest = df.iloc[-1]

    for column in expected_columns:

        assert pd.notna(latest[column])