import pandas as pd

from config.config_loader import ConfigLoader
from repositories.parquet_repository import (
    ParquetRepository,
)


class CalendarService:

    def __init__(self):

        config = ConfigLoader.load()

        self.rebalance_day = (
            config["strategy"][
                "rebalance_day"
            ]
        )

        self.repository = (
            ParquetRepository(
                root="data/indices"
            )
        )

        market_filter = config[
            "universe"
        ][
            "market_filter"
        ]

        self.index_name = (
            market_filter[
                "index"
            ][
                "name"
            ]
        )

        self.index_symbol = (
            market_filter[
                "index"
            ][
                "symbol"
            ]
        )

    def rebalance_dates(
        self,
        start_date,
        end_date,
    ):

        df = self.repository.load(
            self.index_name
        )

        df = df[
            (df["Date"] >= start_date)
            &
            (df["Date"] <= end_date)
        ].copy()

        df["Year"] = (
            df["Date"].dt.year
        )

        df["Month"] = (
            df["Date"].dt.month
        )

        dates = []

        for _, month in df.groupby(
            ["Year", "Month"]
        ):

            if len(month) < self.rebalance_day:
                continue

            dates.append(

                month.iloc[
                    self.rebalance_day - 1
                ]["Date"]

            )

        return dates