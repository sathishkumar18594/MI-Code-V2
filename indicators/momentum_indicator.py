import pandas as pd

from indicators.base_indicator import BaseIndicator


class MomentumIndicator(BaseIndicator):

    def __init__(self):

        super().__init__()

        self.windows = (
            self.config["momentum"]["windows"]
        )
        self.columns = [
            f"return_{months}m"
            for months in self.windows
        ]

    def calculate(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        df = self.prepare_dataframe(df)

        for window in self.windows:

            periods = self.trading_days(
                window
            )

            df[f"return_{window}m"] = (
                df["Close"]
                .pct_change(periods)
                * 100
            )

        return df