from dataclasses import dataclass
from datetime import datetime

from models.sell_reason import SellReason


@dataclass(slots=True)
class Trade:

    symbol: str

    entry_date: datetime

    entry_rank: int

    exit_date: datetime

    exit_rank: int | None

    entry_price: float

    exit_price: float

    quantity: float

    cost_value: float

    proceeds: float

    gross_realized_pnl: float

    return_pct: float

    brokerage: float

    stt: float

    exchange_charge: float

    sebi_charge: float

    gst: float

    stamp_duty: float

    total_charges: float

    net_realized_pnl: float

    holding_days: int

    sell_reason: SellReason