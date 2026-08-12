from dataclasses import dataclass, field

from models.portfolio import Portfolio


@dataclass(slots=True)
class PortfolioAccount:

    portfolio: Portfolio

    initial_capital: float

    cash: float

    equity: float

    total_value: float

    realized_pnl: float = 0.0

    unrealized_pnl: float = 0.0