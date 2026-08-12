from pathlib import Path

import pandas as pd

from repositories.base_repository import BaseRepository


class ParquetRepository(BaseRepository):

    def __init__(self, root="data/prices"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._latest_trading_date = None

    def save(self, symbol: str, df: pd.DataFrame):

        file_path = self.root / f"{symbol}.parquet"
        print(f"Saving -> {file_path}")

        # Ensure Date is datetime
        df["Date"] = pd.to_datetime(df["Date"])

        if file_path.exists():

            existing_df = pd.read_parquet(file_path)

            existing_df["Date"] = pd.to_datetime(existing_df["Date"])

            df = pd.concat(
                [existing_df, df],
                ignore_index=True
            )

            df = df.drop_duplicates(
                subset=["Date"],
                keep="last"
            )

            df = df.sort_values("Date")

            df.reset_index(
                drop=True,
                inplace=True
            )

        df.to_parquet(
            file_path,
            index=False
        )
        # Invalidate cached latest trading date.
        self._latest_trading_date = None

    def load(self, symbol: str) -> pd.DataFrame:

        file_path = self.root / f"{symbol}.parquet"

        return pd.read_parquet(file_path)

    def exists(self, symbol: str) -> bool:

        file_path = self.root / f"{symbol}.parquet"

        return file_path.exists()

    def last_date(self, symbol: str):

        df = self.load(symbol)

        return pd.Timestamp(df["Date"].max()).normalize()

    def latest_trading_date(self):
        if self._latest_trading_date is not None:
            return self._latest_trading_date

        latest = None

        for file_path in self.root.glob("*.parquet"):

            symbol = file_path.stem

            try:
                current = self.last_date(symbol)
            except (FileNotFoundError, ValueError):
                continue

            if latest is None or current > latest:
                latest = current

        self._latest_trading_date = latest

        return self._latest_trading_date