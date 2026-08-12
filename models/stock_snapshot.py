from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class StockSnapshot:

    symbol: str

    date: datetime

    close: float

    average_daily_traded_value: float

    return_3m: float

    return_6m: float

    return_9m: float

    volatility_3m: float

    score: float
