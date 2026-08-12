from dataclasses import dataclass, field
from datetime import datetime

from models.holding import Holding
from models.trade import Trade


@dataclass(slots=True)
class MonthlySnapshot:

    rebalance_date: datetime

    opening_value: float

    closing_value: float

    cash: float

    invested_value: float

    realized_pnl: float

    unrealized_pnl: float

    buys: list[Holding] = field(
        default_factory=list
    )

    sells: list[Trade] = field(
        default_factory=list
    )

    holdings: list[Holding] = field(
        default_factory=list
    )