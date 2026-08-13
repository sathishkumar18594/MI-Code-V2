from dataclasses import dataclass


@dataclass(slots=True)
class StockSummaryReport:

    symbol: str
    market_cap_crore: float | None
    industry: str | None
    total_invested_amount: float
    closed_invested_amount: float
    open_invested_amount: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_return_pct: float
    closed_trades: int
    winning_trades: int
    losing_trades: int
    total_transaction_cost: float
    open_market_value: float
