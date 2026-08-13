from types import SimpleNamespace

import pandas as pd

from models.sell_reason import SellReason
from models.trade import Trade
from services.report_builder import ReportBuilder


def test_completed_sell_retains_full_transaction_details():
    trade = Trade(
        symbol="ABC",
        entry_date=pd.Timestamp("2026-07-10"),
        entry_rank=3,
        exit_date=pd.Timestamp("2026-08-24"),
        exit_rank=72,
        entry_price=100.0,
        exit_price=125.0,
        quantity=10.0,
        cost_value=1_000.0,
        proceeds=1_250.0,
        gross_realized_pnl=250.0,
        return_pct=0.25,
        brokerage=0.0,
        stt=1.25,
        exchange_charge=0.04,
        sebi_charge=0.0,
        gst=0.01,
        stamp_duty=0.0,
        total_charges=1.30,
        net_realized_pnl=248.70,
        holding_days=45,
        sell_reason=SellReason.RANK_EXIT,
    )
    portfolio = SimpleNamespace(
        rebalance_date=pd.Timestamp("2026-08-24"),
        trades=[trade],
        holdings=[],
        total_value=1_100_000.0,
        cash=125_000.0,
    )
    result = SimpleNamespace(periods=[SimpleNamespace(portfolio=portfolio)])

    builder = ReportBuilder.__new__(ReportBuilder)
    builder.market_cap_service = SimpleNamespace(
        market_cap_as_of=lambda symbol, date: 12_500.0,
        industry_as_of=lambda symbol, date: "Industrials",
    )
    decisions = builder._build_decisions(result)

    assert len(decisions) == 1
    sell = decisions[0]
    assert sell.action == "SELL"
    assert sell.decision_date == pd.Timestamp("2026-08-24")
    assert sell.rank_before == 3
    assert sell.rank_after == 72
    assert sell.quantity == 10.0
    assert sell.entry_price == 100.0
    assert sell.exit_price == 125.0
    assert sell.trade_value == 1_250.0
    assert sell.transaction_cost == 1.30
    assert sell.gross_realized_pnl == 250.0
    assert sell.net_realized_pnl == 248.70
    assert sell.return_pct == 0.25
    assert sell.holding_days == 45
    assert sell.market_cap_crore == 12_500.0
    assert sell.industry == "Industrials"
