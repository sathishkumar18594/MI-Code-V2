from dataclasses import dataclass, field
from datetime import datetime

from models.holding import Holding
from models.trade import Trade


@dataclass(slots=True)
class Portfolio:

    rebalance_date: datetime

    initial_capital: float = 0.0

    holdings: list[Holding] = field(
        default_factory=list
    )

    trades: list[Trade] = field(
        default_factory=list
    )

    cash: float = 0.0

    available_cash: float = 0.0

    invested_value: float = 0.0

    total_value: float = 0.0

    realized_pnl: float = 0.0

    period_realized_pnl: float = 0.0

    unrealized_pnl: float = 0.0


    buy_transaction_costs: float = 0.0

    sell_transaction_costs: float = 0.0

    transaction_costs: float = 0.0

    turnover: float = 0.0

    buy_value: float = 0.0

    sell_value: float = 0.0

    is_invested: bool = False