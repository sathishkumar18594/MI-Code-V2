import pandas as pd

from application.app_context import AppContext


class LiquidityService:

    def __init__(
        self,
        context: AppContext,
    ):

        config = context.config.get(
            "liquidity",
            {},
        )

        self.window = config.get(
            "average_daily_traded_value_window",
            20,
        )
        self.minimum_average_daily_traded_value = config.get(
            "min_average_daily_traded_value",
            0.0,
        )

    def average_daily_traded_value(
        self,
        history: pd.DataFrame,
    ) -> float:

        traded_value = (
            history["Close"]
            * history["Volume"]
        )

        return float(
            traded_value.tail(self.window).mean()
        )

    def filter(
        self,
        universe: pd.DataFrame,
    ) -> pd.DataFrame:

        return universe[
            universe["average_daily_traded_value"]
            >= self.minimum_average_daily_traded_value
        ].copy()
