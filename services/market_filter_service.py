import pandas as pd

from application.app_context import AppContext
from indicators.supertrend_indicator import (
    SupertrendIndicator,
)
from utils.timeframe_converter import (
    TimeframeConverter,
)


class MarketFilterService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        self.repository = (
            context.index_repository
        )

        self.market_filter = (
            context.config["universe"]["market_filter"]
        )

        self.enabled = self.market_filter.get("enabled", False)
        if not self.enabled:
            self.latest_market_date = None
            self.market_data = pd.DataFrame()
            return

        self.index_name = (
            self.market_filter["index"]["name"]
        )

        self.index_symbol = (
            self.market_filter["index"]["symbol"]
        )

        self.timeframe = (
            self.market_filter["timeframe"]
        )

        #
        # Load index only once
        #
        df = self.repository.load(
            self.index_name
        )
        self.latest_market_date = pd.Timestamp(df["Date"].max()).normalize()

        #
        # Convert timeframe only once
        #
        self.market_data = (
            TimeframeConverter.convert(
                df=df,
                timeframe=self.timeframe,
            )
        )

        #
        # Calculate Supertrend only once
        #
        supertrend = self.market_filter[
            "supertrend"
        ]

        self.market_data = (
            SupertrendIndicator().execute(
                self.market_data,
                period=supertrend["period"],
                multiplier=supertrend["multiplier"],
            )
        )

    def is_bullish(
        self,
        rebalance_date: pd.Timestamp,
    ) -> bool:

        if not self.enabled:
            return True

        completed = self.market_data[
            self.market_data["Date"] <= rebalance_date
        ]

        # The final resampled weekly row is still in progress when the latest
        # available daily session is before Friday.  It must not be used for a
        # live decision; historical rows are already complete because later
        # daily data exists.  A completed holiday-shortened historical week is
        # retained with its actual final session date.
        if (
            self.timeframe == "WEEKLY"
            and not completed.empty
            and completed.iloc[-1]["Date"] == self.latest_market_date
            and self.latest_market_date.dayofweek != 4
        ):
            completed = completed.iloc[:-1]

        if completed.empty:

            return False

        return bool(
            completed.iloc[-1]["trend"] == 1
        )
