import pandas as pd

from indicators.volatility_indicator import VolatilityIndicator


def test_volatility_indicator():

    df = pd.read_parquet(
        "data/prices/RELIANCE.parquet"
    )

    indicator = VolatilityIndicator()

    df = indicator.execute(df)

    assert "volatility_3m" in df.columns

    latest = df.iloc[-1]

    assert pd.notna(
        latest["volatility_3m"]
    )