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

    market_cap_crore: float | None = None

    industry: str | None = None

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

    gross_realized_pnl: float | None = None

    net_realized_pnl: float | None = None

    return_pct: float | None = None

    holding_days: int | None = None

    notes: str = ""
