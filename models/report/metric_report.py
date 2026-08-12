

from dataclasses import dataclass


@dataclass(slots=True)
class MetricReport:

    initial_capital: float

    final_portfolio_value: float

    absolute_return: float

    cagr: float

    xirr: float

    annualized_volatility: float

    sharpe_ratio: float

    sortino_ratio: float

    calmar_ratio: float

    max_drawdown: float

    max_drawdown_duration: int

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    profit_factor: float

    expectancy: float

    average_trade_return: float

    average_winning_trade: float

    average_losing_trade: float

    largest_winning_trade: float

    largest_losing_trade: float

    average_holding_days: float

    median_holding_days: float

    total_buy_value: float

    total_sell_value: float

    portfolio_turnover: float

    total_buy_transaction_costs: float

    total_sell_transaction_costs: float

    total_transaction_costs: float

    transaction_cost_drag: float