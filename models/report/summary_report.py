

from dataclasses import dataclass


@dataclass(slots=True)
class SummaryReport:

    strategy_name: str

    benchmark_name: str

    universe: str

    portfolio_size: int

    rebalance_frequency: str

    market_filter: str

    initial_capital: float

    final_portfolio_value: float

    absolute_return: float

    cagr: float

    xirr: float

    max_drawdown: float

    sharpe_ratio: float

    sortino_ratio: float

    calmar_ratio: float

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    profit_factor: float

    average_holding_days: float

    portfolio_turnover: float

    total_transaction_costs: float