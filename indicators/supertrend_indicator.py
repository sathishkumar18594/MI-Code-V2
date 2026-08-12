import pandas as pd

from indicators.base_indicator import BaseIndicator


class SupertrendIndicator(BaseIndicator):

    name = "Supertrend"

    columns = [
        "tr",
        "atr",
        "hl2",
        "basic_upper_band",
        "basic_lower_band",
        "final_upper_band",
        "final_lower_band",
        "trend",
        "supertrend",
    ]


    def _calculate_true_range(self, df):
        previous_close = df["Close"].shift(1)

        tr1 = df["High"] - df["Low"]

        tr2 = (
            df["High"] - previous_close
        ).abs()

        tr3 = (
            df["Low"] - previous_close
        ).abs()

        df["tr"] = pd.concat(
            [tr1, tr2, tr3],
            axis=1,
        ).max(axis=1)

    def _calculate_atr(self, df):
        df["atr"] = (
            df["tr"]
            .ewm(
                alpha=1 / self.period,
                adjust=False,
            )
            .mean()
        )

    def _calculate_basic_bands(self, df):
        df["hl2"] = (
            df["High"] + df["Low"]
        ) / 2

        df["basic_upper_band"] = (
            df["hl2"]
            + (self.multiplier * df["atr"])
        )

        df["basic_lower_band"] = (
            df["hl2"]
            - (self.multiplier * df["atr"])
        )

    def _calculate_final_bands(self, df):
        df["final_upper_band"] = float("nan")
        df["final_lower_band"] = float("nan")

        df.loc[df.index[0], "final_upper_band"] = df.loc[
            df.index[0],
            "basic_upper_band",
        ]

        df.loc[df.index[0], "final_lower_band"] = df.loc[
            df.index[0],
            "basic_lower_band",
        ]

        for i in range(1, len(df)):

            previous = i - 1

            if (
                df.loc[i, "basic_upper_band"]
                < df.loc[previous, "final_upper_band"]
                or
                df.loc[previous, "Close"]
                > df.loc[previous, "final_upper_band"]
            ):

                df.loc[i, "final_upper_band"] = (
                    df.loc[i, "basic_upper_band"]
                )

            else:

                df.loc[i, "final_upper_band"] = (
                    df.loc[previous, "final_upper_band"]
                )

            if (
                df.loc[i, "basic_lower_band"]
                > df.loc[previous, "final_lower_band"]
                or
                df.loc[previous, "Close"]
                < df.loc[previous, "final_lower_band"]
            ):

                df.loc[i, "final_lower_band"] = (
                    df.loc[i, "basic_lower_band"]
                )

            else:

                df.loc[i, "final_lower_band"] = (
                    df.loc[previous, "final_lower_band"]
                )

    def _calculate_supertrend(self, df):
        df["trend"] = 1
        df["supertrend"] = float("nan")

        # Initial candle
        df.loc[df.index[0], "supertrend"] = df.loc[
            df.index[0],
            "final_lower_band",
        ]

        for i in range(1, len(df)):

            previous = i - 1

            previous_supertrend = df.loc[
                previous,
                "supertrend",
            ]

            previous_upper = df.loc[
                previous,
                "final_upper_band",
            ]

            previous_lower = df.loc[
                previous,
                "final_lower_band",
            ]

            current_close = df.loc[i, "Close"]

            # TradingView transition logic
            if previous_supertrend == previous_upper:

                if current_close <= df.loc[i, "final_upper_band"]:
                    df.loc[i, "supertrend"] = df.loc[
                        i,
                        "final_upper_band",
                    ]
                    df.loc[i, "trend"] = -1
                else:
                    df.loc[i, "supertrend"] = df.loc[
                        i,
                        "final_lower_band",
                    ]
                    df.loc[i, "trend"] = 1

            else:

                if current_close >= df.loc[i, "final_lower_band"]:
                    df.loc[i, "supertrend"] = df.loc[
                        i,
                        "final_lower_band",
                    ]
                    df.loc[i, "trend"] = 1
                else:
                    df.loc[i, "supertrend"] = df.loc[
                        i,
                        "final_upper_band",
                    ]
                    df.loc[i, "trend"] = -1

    def calculate(
        self,
        df: pd.DataFrame,
        period: int = 1,
        multiplier: float = 2.5,
    ) -> pd.DataFrame:

        df = self.prepare_dataframe(df)
        self.period = period
        self.multiplier = multiplier

        self._calculate_true_range(df)
        self._calculate_atr(df)
        self._calculate_basic_bands(df)
        self._calculate_final_bands(df)
        self._calculate_supertrend(df)

        return df