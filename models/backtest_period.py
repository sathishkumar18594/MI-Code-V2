from dataclasses import dataclass

from models.portfolio import Portfolio
from models.portfolio_performance import (
    PortfolioPerformance,
)


@dataclass(slots=True)
class BacktestPeriod:

    portfolio: Portfolio

    performance: PortfolioPerformance