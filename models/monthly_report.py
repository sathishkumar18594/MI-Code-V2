from dataclasses import dataclass
from datetime import datetime

from models.portfolio import Portfolio


@dataclass(slots=True)
class MonthlyReport:

    rebalance_date: datetime

    execution_date: datetime

    monthly_return: float

    portfolio_value: float

    portfolio: Portfolio