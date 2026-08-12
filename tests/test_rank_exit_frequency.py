from types import SimpleNamespace

import pandas as pd

from models.portfolio import Portfolio
from models.portfolio_position import PortfolioPosition
from services.portfolio_manager import PortfolioManager


def position(symbol="HELD", rank=1):
    return PortfolioPosition(
        symbol=symbol,
        entry_date=pd.Timestamp("2026-01-02"),
        entry_rank=rank,
        entry_price=100.0,
        quantity=10.0,
        current_price=100.0,
        weight=1.0,
        rank=rank,
        score=1.0,
        cost_value=1_000.0,
        market_value=1_000.0,
    )


def ranking(symbol="HELD", rank=99):
    return SimpleNamespace(
        rank=rank,
        stock=SimpleNamespace(symbol=symbol, score=0.1),
    )


def daily_manager():
    manager = PortfolioManager.__new__(PortfolioManager)
    manager.portfolio_size = 10
    manager._apply_corporate_actions = lambda holding, date: None
    manager._mark_to_market = lambda holding, date: None
    manager._update_weights = lambda holdings: None
    return manager


def test_daily_processing_keeps_holding_below_rank_threshold():
    manager = daily_manager()
    manager._build_portfolio = lambda previous, date, holdings, cash, pnl: SimpleNamespace(
        holdings=holdings,
        cash=cash,
        period_realized_pnl=pnl,
    )
    manager._sell_holding = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("rank exit must not run between rebalances")
    )
    portfolio = Portfolio(
        rebalance_date=pd.Timestamp("2026-01-02"),
        holdings=[position()],
        cash=250.0,
    )

    result = manager._process_daily_portfolio(
        portfolio,
        [ranking(rank=99)],
        pd.Timestamp("2026-01-05"),
    )

    assert [holding.symbol for holding in result.holdings] == ["HELD"]
    assert result.holdings[0].rank == 99
    assert result.cash == 250.0
    assert result.period_realized_pnl == 0.0


def test_daily_processing_keeps_holding_missing_from_rankings():
    manager = daily_manager()
    manager._build_portfolio = lambda previous, date, holdings, cash, pnl: SimpleNamespace(
        holdings=holdings,
    )
    held = position(rank=7)
    portfolio = Portfolio(
        rebalance_date=pd.Timestamp("2026-01-02"),
        holdings=[held],
    )

    result = manager._process_daily_portfolio(
        portfolio,
        [],
        pd.Timestamp("2026-01-05"),
    )

    assert result.holdings == [held]
    assert result.holdings[0].rank == 7


def test_rebalance_processing_still_applies_rank_exit():
    manager = PortfolioManager.__new__(PortfolioManager)
    manager._apply_corporate_actions = lambda holding, date: None
    manager._mark_to_market = lambda holding, date: None
    manager.transaction_cost = SimpleNamespace(
        calculate_sell=lambda value: SimpleNamespace(total=0.0),
    )
    sold = []
    manager._sell_holding = lambda portfolio, holding, date, reason, exit_rank: (
        sold.append((holding.symbol, exit_rank)) or holding.market_value
    )
    held = position(rank=1)
    portfolio = Portfolio(
        rebalance_date=pd.Timestamp("2026-01-02"),
        holdings=[held],
    )

    kept, _, cash, _, _ = manager._process_existing_holdings(
        portfolio=portfolio,
        rank_lookup={"HELD": ranking(rank=99)},
        sell_rank=10,
        rebalance_date=pd.Timestamp("2026-01-21"),
        available_cash=0.0,
        debug_dates=set(),
    )

    assert kept == []
    assert sold == [("HELD", 99)]
    assert cash == 1_000.0
