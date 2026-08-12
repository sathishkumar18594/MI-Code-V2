import numpy as np
import pandas as pd

from indicators.base_indicator import BaseIndicator


class VolatilityIndicator(BaseIndicator):

    name = "Volatility"

    columns = []

    def __init__(self):

        super().__init__()

        volatility = self.config["volatility"]

        self.window = volatility["window"]
        self.columns = [
            f"volatility_{self.window}m",
        ]

        self.annualized = volatility["annualized"]

    def calculate(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        df = self.prepare_dataframe(df)

        df["daily_return"] = np.log(
            df["Close"] / df["Close"].shift(1)
        )

        volatility = (
            df["daily_return"]
            .rolling(
                self.trading_days(
                    self.window
                )
            )
            .std()
        )

        if self.annualized:

            volatility *= (
                self.annualization_factor()
            )

        value = volatility * 100

        df[
            f"volatility_{self.window}m"
        ] = value

        return df