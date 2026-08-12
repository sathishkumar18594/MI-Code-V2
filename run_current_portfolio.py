from datetime import datetime
import os
import pandas as pd
import csv
from pathlib import Path
from bootstrap import Bootstrap
from services.universe_service import UniverseService
from services.market_filter_service import MarketFilterService
from services.ranking_service import RankingService
from services.current_portfolio_report_builder import CurrentPortfolioReportBuilder
from reports.current_ranking_report_writer import CurrentRankingReportWriter
from services.current_ranking_report_builder import CurrentRankingReportBuilder
from reports.current_portfolio_report_writer import CurrentPortfolioReportWriter
from services.portfolio_manager import PortfolioManager
from models.portfolio_state import PortfolioState
from models.portfolio import Portfolio
from services.backtest_service import BacktestService
from services.report_builder import ReportBuilder


def main():
    bootstrap = Bootstrap()
    context = bootstrap.context
    calendar = bootstrap.signal_calendar_service()

    market_filter = MarketFilterService(
        context
    )

    ranking_service = RankingService(
        context
    )

    portfolio_manager = PortfolioManager(
        context
    )

    report_builder = CurrentPortfolioReportBuilder()
    ranking_report_builder = CurrentRankingReportBuilder(
        ranking_service.scoring_service,
    )
    ranking_report_writer = CurrentRankingReportWriter()
    portfolio_report_writer = CurrentPortfolioReportWriter()

    universe = UniverseService()

    universe_name = context.config[
        "universe"
    ]["name"]

    requested_date = os.getenv("CURRENT_PORTFOLIO_DATE")
    latest_date = (
        pd.Timestamp(requested_date).normalize()
        if requested_date
        else context.price_repository.latest_trading_date()
    )

    # Live selection always uses the latest published constituent list.  The
    # backtest separately uses date-specific historical constituents; only
    # the strategy rules, not the underlying data snapshot, are shared.
    symbols = universe.get_universe(
        universe_name.lower()
    )

    trading_dates = [latest_date]

    ranking_service.build_cache(
        symbols=symbols,
        trading_dates=trading_dates,
    )

    market_bullish = (
        market_filter.is_bullish(
            latest_date
        )
    )

    initial_signal_date = pd.Timestamp(
        context.config["live_tracking"]["initial_signal_date"]
    )
    tracking_dates = calendar.trading_dates(initial_signal_date, latest_date)
    replay = BacktestService(context).run(
        symbols=symbols,
        trading_dates=tracking_dates,
        rebalance_dates=calendar.signal_dates(initial_signal_date, latest_date),
        write_reports=False,
    )
    portfolio = (
        replay.periods[-1].portfolio
        if replay.periods
        else Portfolio(
            rebalance_date=latest_date,
            initial_capital=context.config["portfolio"]["initial_capital"],
            cash=context.config["portfolio"]["initial_capital"],
            available_cash=context.config["portfolio"]["initial_capital"],
            total_value=context.config["portfolio"]["initial_capital"],
        )
    )

    # Preserve the complete action ledger from the configured live portfolio
    # start date.  current_actions.csv remains the small, forward-looking
    # order sheet for the next trading session.
    action_history = ReportBuilder(context)._build_decisions(replay)
    signal_date_by_execution_date = {
        pd.Timestamp(tracking_dates[index]).normalize(): (
            pd.Timestamp(tracking_dates[index - 1]).normalize()
        )
        for index in range(1, len(tracking_dates))
    }
    action_history.sort(
        key=lambda decision: (
            signal_date_by_execution_date.get(
                pd.Timestamp(decision.decision_date).normalize(),
                pd.Timestamp(decision.decision_date).normalize(),
            ),
            decision.action,
            decision.symbol,
        )
    )
    action_history_file = Path("reports/output/current_action_history.csv")
    with action_history_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Action date", "Scheduled execution", "Action", "Symbol", "Reason", "Rank", "Score",
        ])
        for decision in action_history:
            execution_date = pd.Timestamp(decision.decision_date).normalize()
            action_date = signal_date_by_execution_date.get(
                execution_date,
                execution_date,
            )
            writer.writerow([
                action_date,
                execution_date,
                decision.action,
                decision.symbol,
                decision.reason,
                (
                    decision.rank_after
                    if decision.rank_after is not None
                    else decision.rank_before
                ),
                decision.score,
            ])

    rankings = ranking_service.get_rankings(
        latest_date
    )
    entry_rankings = ranking_service.get_entry_rankings(latest_date)

    execution_date = calendar.next_trading_date(latest_date)
    hedge = context.config.get("market_hedge", {})
    hedge_enabled = hedge.get("enabled", False)
    hedge_symbol = hedge.get("symbol", "GOLDBEES")
    held_symbols = {holding.symbol for holding in portfolio.holdings}
    actions = []

    if not market_bullish:
        # A bearish close is known only after EOD.  Schedule the stock exit and
        # GOLDBEES hedge for the next trading session's open.
        for holding in portfolio.holdings:
            if holding.symbol != hedge_symbol:
                actions.append([
                    "SELL", holding.symbol, holding.rank,
                    execution_date.date(), "Market trend bearish",
                ])
        if hedge_enabled and hedge_symbol not in held_symbols:
            actions.append([
                "BUY", hedge_symbol, 0,
                execution_date.date(), "Market trend bearish hedge",
            ])
    else:
        sell_rank = max(1, int(len(rankings) * 0.10))
        rank_lookup = {
            ranking.stock.symbol: ranking
            for ranking in rankings
        }
        is_hedged = held_symbols == {hedge_symbol}
        is_rebalance_signal = latest_date in set(
            calendar.signal_dates(latest_date, latest_date)
        )

        if is_hedged:
            actions.append([
                "SELL", hedge_symbol, 0,
                execution_date.date(), "Market trend bullish",
            ])

        sells = set()
        if not is_hedged and is_rebalance_signal:
            for holding in portfolio.holdings:
                ranking = rank_lookup.get(holding.symbol)
                if ranking is None or ranking.rank > sell_rank:
                    actions.append([
                        "SELL", holding.symbol,
                        ranking.rank if ranking else "Not ranked",
                        execution_date.date(), "Rank exit",
                    ])
                    sells.add(holding.symbol)

        held_after_sells = held_symbols - sells - {hedge_symbol}
        should_fill = (
            is_hedged
            or not held_symbols
            or is_rebalance_signal
        )
        if should_fill:
            reason = (
                "Market trend bullish"
                if is_hedged
                else "Initial portfolio"
                if not held_symbols
                else "Monthly replacement"
            )
            for ranking in entry_rankings:
                if len(held_after_sells) >= context.config["strategy"]["portfolio_size"]:
                    break
                if ranking.stock.symbol in held_after_sells:
                    continue
                actions.append([
                    "BUY", ranking.stock.symbol, ranking.rank,
                    execution_date.date(), reason,
                ])
                held_after_sells.add(ranking.stock.symbol)

    if not actions:
        actions.append([
            "HOLD", "-", "-", execution_date.date(),
            "No scheduled changes",
        ])

    actions_file = Path("reports/output/current_actions.csv")
    with actions_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Action", "Symbol", "Rank", "Scheduled execution", "Reason"])
        writer.writerows(actions)

    if not market_bullish:
        print()
        print("=" * 60)
        print(f"Market is bearish on {latest_date.date()}.")
        print(f"Actions File  : {actions_file}")
        print(f"Action History: {action_history_file}")
        print("=" * 60)
        print()
        return

    ranking_report = ranking_report_builder.build(
        trading_date=latest_date,
        rankings=entry_rankings,
    )

    ranking_output_file = ranking_report_writer.write(
        ranking_report
    )

    report = report_builder.build(
        trading_date=latest_date,
        portfolio=portfolio,
        rankings=entry_rankings,
    )

    portfolio_output_file = (
        portfolio_report_writer.write(
            report
        )
    )

    print()
    print("=" * 60)
    print("Current Portfolio Generated Successfully")
    print(f"Trading Date : {latest_date.date()}")
    print(f"Rankings File : {ranking_output_file}")
    print(f"Portfolio File: {portfolio_output_file}")
    print(f"Actions File  : {actions_file}")
    print(f"Action History: {action_history_file}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
