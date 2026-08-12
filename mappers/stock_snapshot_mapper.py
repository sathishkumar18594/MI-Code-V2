import pandas as pd

from models.stock_snapshot import StockSnapshot


class StockSnapshotMapper:

    @staticmethod
    def from_series(
        row: pd.Series,
    ) -> StockSnapshot:

        return StockSnapshot(

            symbol=row["symbol"],

            date=row["Date"].to_pydatetime(),

            close=float(row["Close"]),

            average_daily_traded_value=float(
                row["average_daily_traded_value"]
            ),

            return_3m=float(row["return_3m"]),

            return_6m=float(row["return_6m"]),

            # Momentum windows are strategy-configurable.  Preserve the
            # legacy snapshot field for reports when 9m is not selected.
            return_9m=float(row.get("return_9m", float("nan"))),

            volatility_3m=float(
                row["volatility_3m"]
            ),

            score=float(
                row["score"]
            ),
        )
