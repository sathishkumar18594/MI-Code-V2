import pandas as pd

from services.execution_price_service import (
    ExecutionPriceService,
)


def test_execution_price():

    service = ExecutionPriceService()

    execution = service.execution_price(
        symbol="RELIANCE",
        signal_date=pd.Timestamp("2025-01-15"),
    )

    print()

    print(execution)

    assert execution.price > 0

    assert execution.date > pd.Timestamp(
        "2025-01-15"
    )