import pandas as pd

from repositories.parquet_repository import ParquetRepository
from services.market_filter_service import MarketFilterService


def test_market_filter():

    repository = ParquetRepository(
        root="data/indices"
    )

    service = MarketFilterService(
        repository
    )

    bullish = service.is_bullish(
        pd.Timestamp("2026-07-01")
    )

    print()

    print(
        f"Bullish = {bullish}"
    )

    assert isinstance(
        bullish,
        bool,
    )