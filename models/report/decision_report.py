from dataclasses import dataclass
from datetime import datetime

from models.sell_reason import SellReason


@dataclass(slots=True)
class DecisionReport:

    rebalance_date: datetime

    decision_date: datetime

    action: str

    symbol: str

    reason: SellReason | str

    rank_before: int | None = None

    rank_after: int | None = None

    score: float | None = None

    weight_before: float | None = None

    weight_after: float | None = None

    quantity: float | None = None

    entry_price: float | None = None

    exit_price: float | None = None

    trade_value: float | None = None

    transaction_cost: float = 0.0

    portfolio_value: float = 0.0

    cash_after: float = 0.0

    notes: str = ""