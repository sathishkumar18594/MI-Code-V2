import pandas as pd

from services.stock_return_service import (
    StockReturnService,
)


def test_stock_return():

    service = StockReturnService()

    stock_return = service.calculate(
        symbol="RELIANCE",
        entry_signal_date=pd.Timestamp(
            "2025-01-15"
        ),
        exit_signal_date=pd.Timestamp(
            "2025-02-15"
        ),
    )

    print()

    print(stock_return)

    assert isinstance(
        stock_return,
        float,
    )