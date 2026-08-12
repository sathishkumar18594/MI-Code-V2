from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class MarketRegime:

    date: datetime

    close: float

    supertrend: float

    bullish: bool