

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class HoldingReport:

    rebalance_date: datetime

    symbol: str

    market_cap_crore: float | None

    industry: str | None

    rank: int

    score: float

    weight: float

    quantity: float

    entry_date: datetime

    entry_price: float

    current_price: float

    cost_value: float

    market_value: float

    unrealized_pnl: float

    unrealized_return_pct: float

    holding_days: int
