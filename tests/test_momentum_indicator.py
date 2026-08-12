import pandas as pd

from indicators.momentum_indicator import MomentumIndicator


def test_momentum_indicator():

    df = pd.read_parquet(
        "data/prices/RELIANCE.parquet"
    )

    indicator = MomentumIndicator()

    df = indicator.execute(df)

    assert "return_3m" in df.columns
    assert "return_6m" in df.columns
    assert "return_9m" in df.columns

    latest = df.iloc[-1]

    assert pd.notna(latest["return_3m"])
    assert pd.notna(latest["return_6m"])
    assert pd.notna(latest["return_9m"])