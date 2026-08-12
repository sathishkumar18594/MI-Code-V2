from dataclasses import dataclass


@dataclass(slots=True)
class PortfolioPosition:

    symbol: str

    entry_date: object
    entry_rank: int

    entry_price: float

    quantity: float

    current_price: float

    weight: float

    rank: int

    score: float

    cost_value: float

    market_value: float

    realized_pnl: float = 0.0

    unrealized_pnl: float = 0.0
