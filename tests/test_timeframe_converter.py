import pandas as pd

from utils.timeframe_converter import (
    TimeframeConverter,
)


def test_weekly_conversion():

    df = pd.read_parquet(
        "data/prices/RELIANCE.parquet"
    )

    weekly = TimeframeConverter.convert(
        df=df,
        timeframe="WEEKLY",
    )

    assert len(weekly) < len(df)

    assert {
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    }.issubset(
        weekly.columns
    )

    # The final row is timestamped with the latest actual session.
    assert weekly["Date"].iloc[-1] == df["Date"].max()


def test_weekly_conversion_uses_actual_last_trading_session():
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime([
                "2016-04-11", "2016-04-12", "2016-04-13",
                "2016-04-18",
            ]),
            "Open": [100, 101, 102, 103],
            "High": [101, 102, 103, 104],
            "Low": [99, 100, 101, 102],
            "Close": [100, 101, 102, 103],
            "Volume": [10, 10, 10, 10],
        }
    )

    weekly = TimeframeConverter.convert(df, "WEEKLY")

    # 14 and 15 April were exchange holidays, so this weekly bar closed on
    # Wednesday the 13th—not on a synthetic Friday timestamp.
    assert weekly.iloc[0]["Date"] == pd.Timestamp("2016-04-13")

    print()

    print("=" * 80)

    print("Last 10 Weekly Candles")

    print("=" * 80)

    print(
        weekly[
            [
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]
        ].tail(10)
    )
