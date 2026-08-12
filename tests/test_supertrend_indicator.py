import pandas as pd

from indicators.supertrend_indicator import SupertrendIndicator
from utils.timeframe_converter import TimeframeConverter


def test_supertrend_indicator():

    df = pd.read_parquet(
        "data/indices/NIFTY500.parquet"
    )

    weekly = TimeframeConverter.convert(
        df=df,
        timeframe="WEEKLY",
    )

    weekly = SupertrendIndicator().execute(
        weekly
    )

    print()
    print(
        weekly[
            [
                "Date",
                "Close",
                "final_upper_band",
                "final_lower_band",
                "trend",
                "supertrend",
            ]
        ].tail(30)
    )

    assert "tr" in weekly.columns

    assert "atr" in weekly.columns