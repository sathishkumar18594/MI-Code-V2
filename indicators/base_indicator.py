from abc import ABC, abstractmethod

import pandas as pd

from config.config_loader import ConfigLoader


class BaseIndicator(ABC):

    name = "Base Indicator"

    columns = []

    def __init__(self):

        self.config = ConfigLoader.load()

    def prepare_dataframe(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        df = df.copy()

        df["Date"] = pd.to_datetime(df["Date"])

        return (
            df.sort_values("Date")
              .reset_index(drop=True)
        )

    def trading_days(
        self,
        months: int
    ) -> int:

        return (
            months
            * self.config["calendar"]["trading_days_per_month"]
        )

    def annualization_factor(self):

        return (
            self.config["calendar"]["trading_days_per_year"]
            ** 0.5
        )

    def validate_output(
        self,
        df: pd.DataFrame
    ):

        missing = [
            column
            for column in self.columns
            if column not in df.columns
        ]

        if missing:

            raise ValueError(
                f"{self.name} failed. "
                f"Missing columns: {missing}"
            )

    def execute(
        self,
        df: pd.DataFrame,
        **kwargs,
    ) -> pd.DataFrame:

        df = self.calculate(
            df,
            **kwargs,
        )

        self.validate_output(df)

        return df

    @abstractmethod
    def calculate(
        self,
        df: pd.DataFrame,
        **kwargs,
    ) -> pd.DataFrame:
        pass