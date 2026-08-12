from pathlib import Path

import pandas as pd


class IndexRepository:

    def __init__(self):

        self.root = Path("data/indices")

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        name: str,
        df: pd.DataFrame,
    ):

        file_path = self.root / f"{name}.parquet"

        df.to_parquet(
            file_path,
            index=False,
        )

    def load(
        self,
        name: str,
    ) -> pd.DataFrame:

        file_path = self.root / f"{name}.parquet"

        return pd.read_parquet(file_path)

    def exists(
        self,
        name: str,
    ) -> bool:

        return (
            self.root / f"{name}.parquet"
        ).exists()