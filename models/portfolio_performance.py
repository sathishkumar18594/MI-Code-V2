from dataclasses import dataclass


@dataclass(slots=True)
class PortfolioPerformance:

    start_date: object

    end_date: object

    beginning_value: float

    ending_value: float

    period_return: float

    realized_pnl: float

    unrealized_pnl: float

    benchmark_return: float | None = None
    
    period_realized_pnl: float = 0.0
    period_unrealized_pnl: float = 0.0

    @property
    def portfolio_return(self) -> float:
        return self.period_return