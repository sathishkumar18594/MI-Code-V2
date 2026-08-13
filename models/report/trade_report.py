

from dataclasses import dataclass
from datetime import datetime

from models.sell_reason import SellReason


@dataclass(slots=True)
class TradeReport:

    symbol: str

    market_cap_crore: float | None

    industry: str | None

    entry_date: datetime
    entry_rank: int

    exit_date: datetime
    exit_rank: int | None

    holding_days: int

    quantity: float

    entry_price: float

    exit_price: float

    cost_value: float

    proceeds: float

    gross_realized_pnl: float

    brokerage: float

    stt: float

    exchange_charge: float

    sebi_charge: float

    gst: float

    stamp_duty: float

    total_transaction_cost: float

    net_realized_pnl: float

    return_pct: float

    sell_reason: SellReason
