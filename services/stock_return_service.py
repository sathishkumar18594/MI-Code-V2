from application.app_context import AppContext
from services.execution_price_service import (
    ExecutionPriceService,
)
from services.return_calculator import (
    ReturnCalculator,
)


class StockReturnService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        self.execution = (
            ExecutionPriceService(
                context
            )
        )

    def calculate(
        self,
        symbol,
        entry_signal_date,
        exit_signal_date,
    ):

        entry = (
            self.execution.execution_price(
                symbol,
                entry_signal_date,
            )
        )

        exit = (
            self.execution.execution_price(
                symbol,
                exit_signal_date,
            )
        )
        stock_return = ReturnCalculator.simple(
            entry.price,
            exit.price,
        )

        print("=" * 80)
        print(f"Symbol      : {symbol}")
        print(f"Entry Signal: {entry_signal_date}")
        print(f"Entry Exec  : {entry.date} @ {entry.price}")
        print(f"Exit Signal : {exit_signal_date}")
        print(f"Exit Exec   : {exit.date} @ {exit.price}")
        print(f"Return      : {stock_return:.4%}")

        return stock_return