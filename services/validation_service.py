import pandas as pd


class ValidationService:

    REQUIRED_COLUMNS = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    def validate(self, df):

        self.check_columns(df)
        self.check_duplicates(df)
        self.check_nulls(df)
        self.check_negative_prices(df)
        self.check_sorting(df)

    def check_columns(self, df):

        missing = set(self.REQUIRED_COLUMNS) - set(df.columns)

        if missing:
            raise ValueError(
                f"Missing columns : {missing}"
            )

    def check_duplicates(self, df):

        if df["Date"].duplicated().any():
            raise ValueError("Duplicate dates found.")

    def check_nulls(self, df):

        if df.isnull().values.any():
            raise ValueError("Null values found.")

    def check_negative_prices(self, df):

        price_columns = [
            "Open",
            "High",
            "Low",
            "Close"
        ]

        for column in price_columns:

            if (df[column] <= 0).any():
                raise ValueError(
                    f"Invalid prices in {column}"
                )

    def check_sorting(self, df):

        if not df["Date"].is_monotonic_increasing:
            raise ValueError("Dates are not sorted.")