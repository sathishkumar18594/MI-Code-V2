from application.app_context import AppContext
from services.backtest_service import (
    BacktestService,
)
from services.signal_calendar_service import (
    SignalCalendarService,
)


class Bootstrap:

    def __init__(self):

        self.context = AppContext()

    def backtest_service(
        self,
    ) -> BacktestService:

        return BacktestService(
            self.context
        )

    def signal_calendar_service(
        self,
    ) -> SignalCalendarService:

        return SignalCalendarService(
            self.context
        )