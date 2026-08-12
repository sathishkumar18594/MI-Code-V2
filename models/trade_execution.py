from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TradeExecution:

    date: datetime

    price: float