

from dataclasses import dataclass


@dataclass(slots=True)
class AnnualReport:

    year: int

    beginning_value: float

    ending_value: float

    annual_return: float

    realized_pnl: float

    unrealized_pnl: float

    buy_value: float

    sell_value: float

    turnover: float

    buy_transaction_costs: float

    sell_transaction_costs: float

    transaction_costs: float

    trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    profit_factor: float

    max_drawdown: float