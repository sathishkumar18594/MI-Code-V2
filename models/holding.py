from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Holding:

    symbol: str

    entry_date: datetime

    entry_price: float

    quantity: float

    current_price: float

    current_rank: int

    current_score: float

    weight: float

    cost_value: float

    market_value: float

    realized_pnl: float

    unrealized_pnl: float