from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TransactionCostReport:

    rebalance_date: datetime

    buy_value: float

    sell_value: float

    brokerage: float

    stt: float

    exchange_charge: float

    sebi_charge: float

    gst: float

    stamp_duty: float

    total_transaction_cost: float

    transaction_cost_pct: float
