from dataclasses import dataclass, field

from models.backtest_metrics import (
    BacktestMetrics,
)
from models.backtest_period import (
    BacktestPeriod,
)
from models.monthly_report import (
    MonthlyReport,
)


@dataclass(slots=True)
class BacktestResult:

    periods: list[BacktestPeriod]

    metrics: BacktestMetrics | None = None

    monthly_reports: list[MonthlyReport] = field(
        default_factory=list
    )