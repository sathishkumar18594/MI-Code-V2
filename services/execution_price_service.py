from models.trade_execution import TradeExecution
from application.app_context import AppContext


class ExecutionPriceService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        self.repository = (
            context.price_repository
        )
        self._cache = {}
        self._price_cache = {}
        self._index_cache = {}

    def _prices(
        self,
        symbol,
    ):
        if symbol not in self._price_cache:
            df = self.repository.load(symbol)

            dates = df["Date"]

            # Ensure searchsorted operates on pandas datetime values.
            if not hasattr(dates, "searchsorted"):
                dates = df.index

            self._price_cache[symbol] = {
                "dates": dates,
                "opens": df["Open"].to_numpy(),
                "frame": df,
            }

        return self._price_cache[symbol]

    def execution_price(
        self,
        symbol,
        signal_date,
    ) -> TradeExecution:

        signal_date = signal_date.normalize()

        cache_key = (symbol, signal_date)
        index = self._index_cache.get(cache_key)

        if cache_key in self._cache:
            return self._cache[cache_key]

        prices = self._prices(symbol)
        dates = prices["dates"]
        opens = prices["opens"]

        # Locate the first trading session on or after the
        # requested signal date using binary search only once.
        if index is None:
            index = dates.searchsorted(signal_date)
            self._index_cache[cache_key] = index

        if index >= len(dates):

            raise ValueError(
                f"No execution price found for {symbol} after {signal_date}"
            )

        # Execute at the first available trading session on or
        # after the requested signal date.
        execution = TradeExecution(
            date=dates.iloc[index].to_pydatetime()
            if hasattr(dates, "iloc")
            else dates[index].to_pydatetime(),
            price=float(opens[index]),
        )

        self._cache[cache_key] = execution

        return execution

    def closing_price(
        self,
        symbol,
        signal_date,
    ) -> TradeExecution:
        """Return the closing price for the session used for valuation.

        Trade execution deliberately uses the session open.  Reporting a
        daily holding, however, must use that day's close so its market value
        and unrealized P&L reflect the end-of-day position.
        """
        signal_date = signal_date.normalize()
        cache_key = (symbol, signal_date, "close")

        if cache_key in self._cache:
            return self._cache[cache_key]

        prices = self._prices(symbol)
        dates = prices["dates"]
        frame = prices["frame"]
        index = dates.searchsorted(signal_date)

        if index >= len(dates):
            raise ValueError(
                f"No closing price found for {symbol} after {signal_date}"
            )

        execution = TradeExecution(
            date=dates.iloc[index].to_pydatetime()
            if hasattr(dates, "iloc")
            else dates[index].to_pydatetime(),
            price=float(frame["Close"].iloc[index]),
        )
        self._cache[cache_key] = execution

        return execution
