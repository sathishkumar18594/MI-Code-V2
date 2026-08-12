from dataclasses import dataclass, field

from models.portfolio import Portfolio
from domain.monthly_snapshot import (
    MonthlySnapshot,
)


@dataclass(slots=True)
class Account:

    initial_capital: float

    cash: float

    portfolio: Portfolio

    snapshots: list[
        MonthlySnapshot
    ] = field(
        default_factory=list
    )

    equity: float = 0.0

    realized_pnl: float = 0.0

    unrealized_pnl: float = 0.0

    total_value: float = 0.0