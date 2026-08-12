import pandas as pd


class TimeframeConverter:

    _RESAMPLE_RULES = {
        "WEEKLY": "W-FRI",
        "MONTHLY": "ME",
    }

    @classmethod
    def convert(
        cls,
        df: pd.DataFrame,
        timeframe: str,
    ) -> pd.DataFrame:

        if timeframe not in cls._RESAMPLE_RULES:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        result = df.copy()

        result["Date"] = pd.to_datetime(result["Date"])

        result = result.sort_values("Date")

        result = result.set_index("Date")

        # Keep the existing monthly timestamp convention.  Weekly candles use
        # their actual last trading session, which can be earlier than Friday
        # in a holiday-shortened week.
        if timeframe == "MONTHLY":
            result["PeriodStart"] = result.index
        else:
            result["PeriodEnd"] = result.index

        aggregations = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
        if timeframe == "MONTHLY":
            aggregations["PeriodStart"] = "first"
        else:
            aggregations["PeriodEnd"] = "last"
        result = (
            result
            .resample(cls._RESAMPLE_RULES[timeframe])
            .agg(aggregations)
            .dropna()
            .reset_index()
        )

        if timeframe == "MONTHLY":
            result["Date"] = result.pop("PeriodStart")
        else:
            result["Date"] = result.pop("PeriodEnd")

        # A weekly signal is dated at the actual final session used in its
        # OHLC data.  This prevents Monday look-ahead and supports weeks that
        # end before Friday because of exchange holidays.

        return result
