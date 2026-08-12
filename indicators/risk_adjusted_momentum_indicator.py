import pandas as pd

from indicators.base_indicator import BaseIndicator


class RiskAdjustedMomentumIndicator(BaseIndicator):

    name = "Risk Adjusted Momentum"

    columns = [
        "momentum_score"
    ]

    def __init__(self):

        super().__init__()

        self.windows = self.config["momentum"]["windows"]

        self.volatility_window = self.config["volatility"]["window"]

    def calculate(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        df = self.prepare_dataframe(df)

        return_columns = [
            f"return_{window}m"
            for window in self.windows
        ]

        df["momentum_score"] = (
            df[return_columns].sum(axis=1)
            / df[f"volatility_{self.volatility_window}m"]
        )

        # Prevent division by zero / infinity
        df["momentum_score"] = (
            df["momentum_score"]
            .replace([float("inf"), float("-inf")], pd.NA)
        )

        return df