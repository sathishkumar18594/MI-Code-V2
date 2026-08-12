from dataclasses import dataclass


@dataclass(slots=True)
class BacktestMetrics:

    initial_capital: float = 0.0
    final_portfolio_value: float = 0.0
    absolute_return: float = 0.0

    total_return: float = 0.0

    annual_return: float = 0.0

    cagr: float = 0.0

    max_drawdown: float = 0.0

    sharpe_ratio: float = 0.0

    sortino_ratio: float = 0.0

    calmar_ratio: float = 0.0

    win_rate: float = 0.0
    xirr: float = 0.0
    annualized_volatility: float = 0.0
    max_drawdown_duration: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    average_trade_return: float = 0.0
    average_winning_trade: float = 0.0
    average_losing_trade: float = 0.0
    largest_winning_trade: float = 0.0
    largest_losing_trade: float = 0.0
    average_holding_days: float = 0.0
    median_holding_days: float = 0.0
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    portfolio_turnover: float = 0.0
    total_buy_transaction_costs: float = 0.0
    total_sell_transaction_costs: float = 0.0
    total_transaction_costs: float = 0.0
    transaction_cost_drag: float = 0.0
