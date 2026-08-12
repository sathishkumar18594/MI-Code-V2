

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MonthlyReport:

    rebalance_date: datetime

    beginning_value: float

    ending_value: float

    monthly_return: float

    cash: float

    invested_value: float

    realized_pnl: float

    unrealized_pnl: float

    buy_value: float

    sell_value: float

    buy_transaction_costs: float

    sell_transaction_costs: float

    transaction_costs: float

    turnover: float

    holdings: int