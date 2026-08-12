"""Standalone daily backtest and reporting for the combined portfolio."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from services.multi_universe_data_service import MultiUniverseDataService
from services.multi_universe_portfolio_manager import MultiUniversePortfolioManager


class MultiUniverseBacktestService:
    def __init__(self, context):
        self.context = context
        config_file = Path(os.getenv(
            "MULTI_UNIVERSE_CONFIG",
            "config/multi_universe_portfolio.yaml",
        ))
        self.config = yaml.safe_load(
            config_file.read_text()
        )
        self.data = MultiUniverseDataService(context, self.config)
        self.manager = MultiUniversePortfolioManager(context, self.config)

    def run(self, trading_dates, rebalance_dates, output_directory="reports/multi_universe"):
        dates = [pd.Timestamp(date).normalize() for date in trading_dates]
        rebalance_dates = {pd.Timestamp(date).normalize() for date in rebalance_dates}
        date_index = {date: index for index, date in enumerate(dates)}
        rebalance_execution_dates = {
            dates[date_index[signal] + 1]
            for signal in rebalance_dates
            if signal in date_index and date_index[signal] + 1 < len(dates)
        }
        self.manager.events = []
        self.data.build(dates)
        sleeves = self.manager.create_sleeves()
        daily_rows, sleeve_rows, holding_rows = [], [], []
        ranking_rows, circuit_rows, rebalance_rows = [], [], []
        rotation_enabled = self.config.get("sector_rotation", {}).get(
            "redeploy_to_bullish", False
        )
        rotation_settings = self.config.get("sector_rotation", {})
        selection_mode = rotation_settings.get("selection_mode")
        managed_sector_mode = selection_mode in {"TOP_RANKED_BULLISH", "FIRST_BULLISH"}
        independent_sector_mode = selection_mode == "ALL_BULLISH"
        sector_stock_mode = managed_sector_mode or independent_sector_mode
        top_ranked_mode = selection_mode == "TOP_RANKED_BULLISH"
        configured_order = [item["universe"] for item in self.config["sleeves"]]
        max_sectors = int(rotation_settings.get("max_selected_sectors", len(self.config["sleeves"])))
        refill_monthly_only = rotation_settings.get("refill_on_monthly_rebalance_only", False)
        lock_sectors_until_bearish = rotation_settings.get(
            "lock_selected_sectors_until_bearish", False
        )
        daily_rank_exit = rotation_settings.get("daily_rank_exit", False)
        previous_bullish = None
        previous_regimes = set()

        for index in range(1, len(dates)):
            date = dates[index]
            signal_date = dates[index - 1]
            bullish_universes = {
                definition["universe"]
                for definition in self.config["sleeves"]
                if self.data.is_bullish(definition["universe"], signal_date)
            }
            if managed_sector_mode:
                candidates = (
                    self.data.sector_rankings(signal_date)
                    if top_ranked_mode else configured_order
                )
                ranked = [item for item in candidates if item in bullish_universes]
                if previous_bullish is None:
                    # Sector ranks are acted on only at the monthly rebalance.
                    deployed_universes = set(ranked[:max_sectors])
                elif lock_sectors_until_bearish:
                    # Once selected, a sector remains in the portfolio until
                    # its independent Supertrend becomes bearish. Monthly
                    # rebalances change stocks inside the sleeve, not sectors.
                    deployed_universes = previous_bullish & bullish_universes
                    for universe in ranked:
                        if len(deployed_universes) >= max_sectors:
                            break
                        if universe not in deployed_universes:
                            deployed_universes.add(universe)
                elif date in rebalance_execution_dates:
                    deployed_universes = set(ranked[:max_sectors])
                else:
                    # Between rebalances retain selected sectors while bullish.
                    # A bearish regime exit immediately promotes the best
                    # bullish sector not already represented.
                    deployed_universes = previous_bullish & bullish_universes
                    for universe in ranked:
                        if len(deployed_universes) >= max_sectors:
                            break
                        deployed_universes.add(universe)
            else:
                deployed_universes = bullish_universes
            # During factor warm-up use the eligible sectors directly.  This
            # fallback must happen before comparing selections, otherwise an
            # empty provisional rank list creates a false daily rotation.
            if rotation_enabled and not deployed_universes:
                deployed_universes = set(sorted(bullish_universes)[:max_sectors])
            prior_deployed = previous_bullish or set()
            newly_selected = deployed_universes - prior_deployed
            retained_sectors = deployed_universes & prior_deployed
            rotation_event = rotation_enabled and (
                previous_bullish is None
                or deployed_universes != previous_bullish
            )

            # Pool capital and redeploy it among every currently bullish
            # sector.  Gold is bought only when no sector has a bullish trend.
            if rotation_event:
                # Liquidations happen before update_sleeve sets its decision
                # date, so explicitly attach the current signal date.
                self.manager.decision_date = signal_date
                for universe, sleeve in sleeves.items():
                    if sleeve.holdings and (not managed_sector_mode or universe not in deployed_universes):
                        self.manager.liquidate(sleeve, date, "SECTOR_ROTATION")
                # Preserve cash belonging to retained sectors (including cash
                # from daily rank exits). Only released/inactive capital funds
                # newly promoted sectors.
                pooled_cash = sum(
                    sleeve.cash for universe, sleeve in sleeves.items()
                    if universe not in retained_sectors
                )
                for universe, sleeve in sleeves.items():
                    if universe not in retained_sectors:
                        sleeve.cash = 0.0
                # With no bullish sector, use the first sleeve only as the
                # cash/hedge carrier.  It remains outside deployed_universes,
                # so the manager buys the configured hedge rather than stocks.
                cash_carrier = next(
                    (item["universe"] for item in self.config["sleeves"]
                     if item["universe"] not in retained_sectors),
                    self.config["sleeves"][0]["universe"],
                )
                capital_receivers = newly_selected or {cash_carrier}
                allocation = pooled_cash / len(capital_receivers)
                for universe in capital_receivers:
                    sleeves[universe].cash = allocation
            else:
                deployed_universes = (
                    set(sleeves)
                    if independent_sector_mode
                    else (previous_bullish or set())
                )

            # Earlier sleeves have priority during a rebalance.  Their kept
            # holdings are reserved before a later sleeve selects replacements.
            reserved_symbols = set()
            for definition in self.config["sleeves"]:
                universe = definition["universe"]
                sleeve = sleeves[universe]
                participates = universe in deployed_universes
                is_monthly_rebalance = date in rebalance_execution_dates
                is_regime_reentry = (
                    independent_sector_mode
                    and universe in bullish_universes
                    and universe not in previous_regimes
                )
                is_sector_rotation_entry = (
                    managed_sector_mode and universe in newly_selected
                )
                # A bullish regime flip opens the sector immediately on this
                # execution session.  Only ordinary vacancy refills (for
                # example after a stop loss) must wait for the monthly date.
                can_fill = (
                    is_monthly_rebalance
                    or is_regime_reentry
                    or is_sector_rotation_entry
                )
                is_decision_day = is_monthly_rebalance or rotation_event
                # Daily rank exits require only the active sleeves. Entry
                # rankings are needed solely when positions may be filled.
                is_rank_evaluation = participates and (
                    (managed_sector_mode and daily_rank_exit)
                    or (independent_sector_mode and daily_rank_exit)
                    or can_fill
                )
                rankings = (
                    self.data.rankings(universe, signal_date)
                    if is_rank_evaluation else []
                )
                entry_rankings = (
                    self.data.rankings(universe, signal_date, entry=True)
                    if can_fill and participates else []
                )
                if (
                    sector_stock_mode
                    and rotation_settings.get("strict_top_rank_entries", False)
                ):
                    # Ranks are assigned across the complete point-in-time
                    # sector universe before entry filters.  Do not promote a
                    # lower-ranked survivor when a true top-N stock fails the
                    # market-cap, liquidity, circuit, or price screen.
                    entry_rankings = [
                        ranking for ranking in entry_rankings
                        if ranking.rank <= sleeve.portfolio_size
                    ]
                reserved_before = set(reserved_symbols)
                if rotation_enabled and not participates:
                    # Capital for inactive sectors has already been deployed
                    # into bullish sectors, so there is no per-sleeve hedge.
                    rankings = []
                    entry_rankings = []
                self.manager.update_sleeve(
                    sleeve=sleeve,
                    market_bullish=participates and universe in bullish_universes,
                    rankings=rankings,
                    entry_rankings=entry_rankings,
                    date=date,
                    is_rebalance_day=(
                        can_fill
                    ),
                    reserved_symbols=reserved_symbols,
                    signal_date=signal_date,
                    evaluate_ranks=is_rank_evaluation,
                    allow_daily_refill=not refill_monthly_only,
                    skip_unpriced_entries=sector_stock_mode,
                    protect_portfolio_ranks=sector_stock_mode,
                    rank_exit_fraction=(
                        rotation_settings.get("rank_exit_fraction")
                        if sector_stock_mode else None
                    ),
                    entry_reason=None,
                    allow_regime_reentry=independent_sector_mode,
                    regime_entry_signal=is_regime_reentry,
                    rank_exit_enabled=rotation_settings.get("rank_exit_enabled", True),
                    stop_loss_pct=rotation_settings.get("stop_loss_pct"),
                )
                if can_fill and participates:
                    eligible = {item.stock.symbol for item in entry_rankings}
                    selected = {
                        item.symbol for item in sleeve.holdings
                        if item.symbol != self.manager.hedge_symbol
                    }
                    for ranking in rankings:
                        symbol = ranking.stock.symbol
                        status = (
                            "SELECTED" if symbol in selected else
                            "DUPLICATE_SKIPPED" if symbol in reserved_before else
                            "ELIGIBLE" if symbol in eligible else "ENTRY_FILTERED"
                        )
                        ranking_rows.append({
                            "date": signal_date, "execution_date": date,
                            "universe": universe,
                            "rank": ranking.rank, "symbol": symbol,
                            "score": ranking.score,
                            **ranking.factor_values,
                            "status": status,
                        })
                        if status in {"SELECTED", "DUPLICATE_SKIPPED", "ENTRY_FILTERED"}:
                            rebalance_rows.append({
                                "decision_date": signal_date, "execution_date": date,
                                "universe": universe,
                                "action": "KEEP" if status == "SELECTED" else "SKIP",
                                "symbol": symbol, "reason": status,
                                "entry_rank": ranking.rank, "score": ranking.score,
                            })
                        if symbol not in eligible:
                            filter_reason = self.data.entry_filter_reason(
                                universe, symbol, signal_date
                            )
                            circuit_rows.append({
                                "date": signal_date, "execution_date": date,
                                "universe": universe,
                                "symbol": symbol, "rank": ranking.rank,
                                "reason": filter_reason,
                                **self.data.circuit_risk(
                                    universe, symbol, signal_date
                                ),
                            })
                for item in sleeve.holdings:
                    holding_rows.append({
                        "date": date, "universe": universe,
                        "symbol": item.symbol, "rank": item.rank,
                        "score": item.score, "entry_date": item.entry_date,
                        "entry_rank": item.entry_rank,
                        "entry_price": item.entry_price,
                        "current_price": item.current_price,
                        "quantity": item.quantity,
                        "cost_value": item.cost_value,
                        "market_value": item.market_value,
                        "unrealized_pnl": item.market_value - item.cost_value,
                        "unrealized_return_pct": (
                            (item.market_value - item.cost_value) / item.cost_value
                            if item.cost_value else 0.0
                        ),
                        "holding_days": (
                            date - pd.Timestamp(item.entry_date).normalize()
                        ).days,
                        "sleeve_weight": item.weight,
                    })
                sleeve_rows.append({
                    "date": date,
                    "universe": universe,
                    "cash": sleeve.cash,
                    "stock_value": sum(
                        item.market_value for item in sleeve.holdings
                        if item.symbol != self.manager.hedge_symbol
                    ),
                    "gold_value": sum(
                        item.market_value for item in sleeve.holdings
                        if item.symbol == self.manager.hedge_symbol
                    ),
                    "total_value": sleeve.value,
                    "holdings": ",".join(item.symbol for item in sleeve.holdings),
                })
            daily_rows.append({
                "date": date,
                "portfolio_value": sum(sleeve.value for sleeve in sleeves.values()),
            })
            previous_bullish = deployed_universes
            previous_regimes = bullish_universes

        daily = pd.DataFrame(daily_rows)
        daily["daily_return"] = daily["portfolio_value"].pct_change().fillna(0.0)
        daily["month"] = daily["date"].dt.to_period("M")
        daily["year"] = daily["date"].dt.year
        monthly = self._period_report(daily, "month")
        annual = self._period_report(daily, "year")
        sleeve_daily = pd.DataFrame(sleeve_rows)
        sleeve_daily["month"] = sleeve_daily["date"].dt.to_period("M")
        sleeve_daily["year"] = sleeve_daily["date"].dt.year
        monthly_sleeves = (
            sleeve_daily.groupby(["month", "universe"], as_index=False)
            .last()[["month", "universe", "cash", "stock_value", "gold_value", "total_value"]]
        )
        monthly_risk = self._monthly_metrics(daily, monthly_sleeves)
        metrics = self._metrics(daily)
        holdings = pd.DataFrame(holding_rows)
        if not holdings.empty:
            combined_value = holdings.groupby("date")["market_value"].transform("sum")
            holdings["weight"] = np.where(
                combined_value > 0, holdings["market_value"] / combined_value, 0.0
            )
        rankings_report = pd.DataFrame(ranking_rows)
        circuit_screen = pd.DataFrame(circuit_rows)
        lower_circuit = circuit_screen[
            circuit_screen["reason"] == "LOWER_CIRCUIT_FILTER"
        ].copy() if not circuit_screen.empty else circuit_screen.copy()
        if not lower_circuit.empty:
            lower_circuit["year"] = pd.to_datetime(lower_circuit["date"]).dt.year
            lower_circuit["filter_trigger_date"] = lower_circuit["date"]
            lower_circuit["consecutive_lower_circuit_days"] = (
                lower_circuit["max_lower_circuit_streak"]
            )
        events = pd.DataFrame(self.manager.events)
        decisions = pd.concat(
            [events, pd.DataFrame(rebalance_rows)], ignore_index=True, sort=False
        )
        trades = self._trades_report(events)
        metrics.update(self._trade_metrics(daily, events, trades))
        monthly_summary = self._period_details(
            daily, sleeve_daily, holdings, events, trades, "month"
        )
        annual = self._period_details(
            daily, sleeve_daily, holdings, events, trades, "year"
        )
        monthly = self._daily_accounting(
            daily, sleeve_daily, holdings, events, trades
        )
        monthly_metrics = monthly_summary.merge(
            monthly_risk[[
                "month", "annualized_volatility", "sharpe_ratio",
                "cash_value", "stock_value", "gold_value",
            ]],
            on="month", how="left",
        )
        transaction_costs = self._transaction_cost_report(events)
        stock_summary = self._stock_summary(trades, holdings)
        annual_asset = self._annual_asset_contribution(sleeve_daily)
        asset_performance = self._asset_class_performance(sleeve_daily)
        holdings.insert(0, "rebalance_date", holdings["date"])
        if not decisions.empty:
            decisions["rebalance_date"] = decisions["execution_date"]
            decisions["rank_before"] = decisions.get("entry_rank")
            decisions["rank_after"] = decisions.get("exit_rank")
            decisions["trade_value"] = decisions.get("gross_value")
            decisions["entry_price"] = np.where(
                decisions["action"] == "BUY", decisions.get("price"), np.nan
            )
            decisions["exit_price"] = np.where(
                decisions["action"] == "SELL", decisions.get("price"), np.nan
            )
            decisions["notes"] = decisions["universe"]
            portfolio_values = daily.set_index("date")["portfolio_value"]
            cash_values = sleeve_daily.set_index(["date", "universe"])["cash"]
            decisions["portfolio_value"] = pd.to_datetime(
                decisions["execution_date"]
            ).map(portfolio_values)
            decisions["cash_after"] = [
                cash_values.get((pd.Timestamp(date), universe), np.nan)
                for date, universe in zip(
                    decisions["execution_date"], decisions["universe"]
                )
            ]
            current_weights = holdings.set_index(
                ["date", "universe", "symbol"]
            )["weight"] if not holdings.empty else {}
            decisions["weight_after"] = [
                current_weights.get(
                    (pd.Timestamp(date), universe, symbol),
                    0.0 if action == "SELL" else np.nan,
                )
                for date, universe, symbol, action in zip(
                    decisions["execution_date"], decisions["universe"],
                    decisions["symbol"], decisions["action"],
                )
            ]
            decisions["weight_before"] = np.nan
        summary = pd.DataFrame([{
            **metrics,
            "strategy_name": "Multi-Universe Momentum",
            "benchmark_name": "Independent sleeve benchmarks",
            "universe": "NIFTY50+NIFTY100+NIFTY200+NIFTY500",
            "portfolio_size": sum(item["portfolio_size"] for item in self.config["sleeves"]),
            "rebalance_frequency": "Monthly",
            "market_filter": "Weekly Supertrend per sleeve",
            "total_buys": int((events.get("action") == "BUY").sum()) if not events.empty else 0,
            "total_sells": int((events.get("action") == "SELL").sum()) if not events.empty else 0,
            "total_transaction_cost": float(events.get("transaction_cost", pd.Series(dtype=float)).sum()),
        }])
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        daily.to_csv(output / "daily_portfolio.csv", index=False)
        sleeve_daily.to_csv(output / "sleeve_daily.csv", index=False)
        monthly.to_csv(output / "monthly.csv", index=False)
        annual.to_csv(output / "annual.csv", index=False)
        monthly_metrics.to_csv(output / "monthly_metrics.csv", index=False)
        self._monthly_return_matrix(monthly_summary).to_csv(
            output / "monthly_return_matrix.csv", index=False
        )
        pd.DataFrame([metrics]).to_csv(output / "metrics.csv", index=False)
        summary.to_csv(output / "summary.csv", index=False)
        holdings.to_csv(output / "holdings.csv", index=False)
        trades.to_csv(output / "trades.csv", index=False)
        decisions.to_csv(output / "decisions.csv", index=False)
        rankings_report.to_csv(output / "rankings.csv", index=False)
        circuit_screen.to_csv(output / "circuit_screen.csv", index=False)
        lower_circuit.to_csv(output / "lower_circuit_filtered_stocks.csv", index=False)
        transaction_costs.to_csv(output / "transaction_costs.csv", index=False)
        stock_summary.to_csv(output / "stock_summary.csv", index=False)
        annual_asset.to_csv(output / "annual_asset_contribution.csv", index=False)
        asset_performance.to_csv(output / "asset_class_performance.csv", index=False)
        return {"daily": daily, "sleeves": sleeve_daily, "metrics": metrics}

    @staticmethod
    def _transaction_cost_report(events):
        if events.empty:
            return events
        data = events.copy()
        data["buy_value"] = np.where(data["action"] == "BUY", data["gross_value"], 0.0)
        data["sell_value"] = np.where(data["action"] == "SELL", data["gross_value"], 0.0)
        report = data.groupby(["execution_date", "universe"], as_index=False).agg(
            buy_value=("buy_value", "sum"), sell_value=("sell_value", "sum"),
            brokerage=("brokerage", "sum"), stt=("stt", "sum"),
            exchange_charge=("exchange_charge", "sum"),
            sebi_charge=("sebi_charge", "sum"), gst=("gst", "sum"),
            stamp_duty=("stamp_duty", "sum"),
            total_transaction_cost=("transaction_cost", "sum"),
        )
        turnover = report["buy_value"] + report["sell_value"]
        report["transaction_cost_pct"] = np.where(
            turnover > 0, report["total_transaction_cost"] / turnover, 0.0
        )
        return report.rename(columns={"execution_date": "rebalance_date"})

    @staticmethod
    def _trades_report(events):
        if events.empty:
            return events
        buys = events[events["action"] == "BUY"][[
            "universe", "symbol", "execution_date", "price",
            "transaction_cost", "cost_value",
        ]].rename(columns={
            "execution_date": "entry_date",
            "price": "entry_price",
            "transaction_cost": "buy_transaction_cost",
            "cost_value": "invested_amount",
        })
        sells = events[events["action"] == "SELL"].copy().rename(columns={
            "execution_date": "exit_date",
            "price": "exit_price",
            "transaction_cost": "sell_transaction_cost",
        })
        trades = sells.merge(
            buys,
            on=["universe", "symbol", "entry_date"],
            how="left",
        )
        trades["total_transaction_cost"] = (
            trades["buy_transaction_cost"].fillna(0.0)
            + trades["sell_transaction_cost"].fillna(0.0)
        )
        trades["net_realized_pnl"] = (
            trades["net_value"]
            - trades["invested_amount"].fillna(trades["cost_value"])
        )
        trades["holding_days"] = (
            pd.to_datetime(trades["exit_date"])
            - pd.to_datetime(trades["entry_date"])
        ).dt.days
        trades["proceeds"] = trades["gross_value"]
        trades["gross_realized_pnl"] = (
            trades["gross_value"]
            - trades["invested_amount"].fillna(trades["cost_value"])
        )
        trades["return_pct"] = (
            trades["net_realized_pnl"]
            / trades["invested_amount"].fillna(trades["cost_value"])
        )
        trades["sell_reason"] = trades["reason"]
        return trades

    @staticmethod
    def _stock_summary(trades, holdings):
        if trades.empty and holdings.empty:
            return pd.DataFrame()
        closed = trades.groupby(["universe", "symbol"], as_index=False).agg(
            closed_invested_amount=("invested_amount", "sum"),
            closed_trades=("symbol", "size"),
            average_closed_holding_days=("holding_days", "mean"),
            max_closed_holding_days=("holding_days", "max"),
            realized_pnl=("net_realized_pnl", "sum"),
            winning_trades=("net_realized_pnl", lambda values: int((values > 0).sum())),
            losing_trades=("net_realized_pnl", lambda values: int((values < 0).sum())),
            total_transaction_cost=("total_transaction_cost", "sum"),
        ) if not trades.empty else pd.DataFrame(columns=["universe", "symbol"])
        latest = holdings[holdings["date"] == holdings["date"].max()].copy()
        opened = latest.groupby(["universe", "symbol"], as_index=False).agg(
            open_invested_amount=("cost_value", "sum"),
            open_market_value=("market_value", "sum"),
            unrealized_pnl=("unrealized_pnl", "sum"),
            current_holding_days=("holding_days", "max"),
        ) if not latest.empty else pd.DataFrame(columns=["universe", "symbol"])
        result = closed.merge(opened, on=["universe", "symbol"], how="outer").fillna(0)
        for column in (
            "closed_invested_amount", "open_invested_amount", "realized_pnl",
            "unrealized_pnl", "total_transaction_cost", "closed_trades",
            "winning_trades", "losing_trades", "open_market_value",
            "average_closed_holding_days", "max_closed_holding_days",
            "current_holding_days",
        ):
            if column not in result:
                result[column] = 0.0
        result["total_invested_amount"] = (
            result["closed_invested_amount"] + result["open_invested_amount"]
        )
        result["total_pnl"] = result["realized_pnl"] + result["unrealized_pnl"]
        result["total_return_pct"] = np.where(
            result["total_invested_amount"] > 0,
            result["total_pnl"] / result["total_invested_amount"], 0.0,
        )
        return result

    def _period_details(self, daily, sleeve_daily, holdings, events, trades, period):
        rows = []
        initial = float(self.config["initial_capital"])
        previous_ending = initial
        for key, values in daily.groupby(period, sort=True):
            ending = float(values.iloc[-1]["portfolio_value"])
            returns = values["daily_return"]
            period_return = float((1.0 + returns).prod() - 1.0)
            sleeve_values = sleeve_daily[sleeve_daily[period] == key]
            last_date = sleeve_values["date"].max()
            ending_sleeves = sleeve_values[sleeve_values["date"] == last_date]
            period_events = events[
                pd.to_datetime(events["execution_date"]).dt.to_period("M") == key
            ] if period == "month" and not events.empty else (
                events[pd.to_datetime(events["execution_date"]).dt.year == key]
                if not events.empty else events
            )
            period_trades = trades[
                pd.to_datetime(trades["exit_date"]).dt.to_period("M") == key
            ] if period == "month" and not trades.empty else (
                trades[pd.to_datetime(trades["exit_date"]).dt.year == key]
                if not trades.empty else trades
            )
            period_holdings = holdings[holdings["date"] == last_date]
            buys = period_events[period_events["action"] == "BUY"] if not period_events.empty else period_events
            sells = period_events[period_events["action"] == "SELL"] if not period_events.empty else period_events
            pnl = period_trades["net_realized_pnl"] if not period_trades.empty else pd.Series(dtype=float)
            peak = values["portfolio_value"].cummax()
            row = {
                period: key,
                "beginning_value": previous_ending,
                "ending_value": ending,
                f"{period}_return": ending / previous_ending - 1 if previous_ending else 0.0,
                "period_return": period_return,
                "cumulative_return": ending / initial - 1,
                "cash": ending_sleeves["cash"].sum(),
                "invested_value": ending_sleeves["stock_value"].sum() + ending_sleeves["gold_value"].sum(),
                "realized_pnl": pnl.sum(),
                "unrealized_pnl": period_holdings["unrealized_pnl"].sum(),
                "buy_value": buys["gross_value"].sum() if not buys.empty else 0.0,
                "sell_value": sells["gross_value"].sum() if not sells.empty else 0.0,
                "buy_transaction_costs": buys["transaction_cost"].sum() if not buys.empty else 0.0,
                "sell_transaction_costs": sells["transaction_cost"].sum() if not sells.empty else 0.0,
                "transaction_costs": period_events["transaction_cost"].sum() if not period_events.empty else 0.0,
                "turnover": (
                    (period_events["gross_value"].sum() / previous_ending)
                    if previous_ending and not period_events.empty else 0.0
                ),
                "holdings": len(period_holdings),
                "trades": len(period_trades),
                "winning_trades": int((pnl > 0).sum()),
                "losing_trades": int((pnl < 0).sum()),
                "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0,
                "profit_factor": (
                    pnl[pnl > 0].sum() / abs(pnl[pnl < 0].sum())
                    if len(pnl[pnl < 0]) and pnl[pnl < 0].sum() else 0.0
                ),
                "max_drawdown": float(-(values["portfolio_value"] / peak - 1).min()),
            }
            rows.append(row)
            previous_ending = ending
        return pd.DataFrame(rows)

    def _daily_accounting(self, daily, sleeve_daily, holdings, events, trades):
        rows = []
        beginning = float(self.config["initial_capital"])
        for _, value in daily.iterrows():
            date = value["date"]
            ending = float(value["portfolio_value"])
            day_sleeves = sleeve_daily[sleeve_daily["date"] == date]
            day_holdings = holdings[holdings["date"] == date]
            day_events = events[
                pd.to_datetime(events["execution_date"]) == date
            ] if not events.empty else events
            day_trades = trades[
                pd.to_datetime(trades["exit_date"]) == date
            ] if not trades.empty else trades
            buys = day_events[day_events["action"] == "BUY"] if not day_events.empty else day_events
            sells = day_events[day_events["action"] == "SELL"] if not day_events.empty else day_events
            rows.append({
                "rebalance_date": date,
                "beginning_value": beginning,
                "ending_value": ending,
                "monthly_return": ending / beginning - 1 if beginning else 0.0,
                "cash": day_sleeves["cash"].sum(),
                "invested_value": day_sleeves["stock_value"].sum() + day_sleeves["gold_value"].sum(),
                "realized_pnl": day_trades["net_realized_pnl"].sum() if not day_trades.empty else 0.0,
                "unrealized_pnl": day_holdings["unrealized_pnl"].sum(),
                "buy_value": buys["gross_value"].sum() if not buys.empty else 0.0,
                "sell_value": sells["gross_value"].sum() if not sells.empty else 0.0,
                "buy_transaction_costs": buys["transaction_cost"].sum() if not buys.empty else 0.0,
                "sell_transaction_costs": sells["transaction_cost"].sum() if not sells.empty else 0.0,
                "transaction_costs": day_events["transaction_cost"].sum() if not day_events.empty else 0.0,
                "turnover": (
                    day_events["gross_value"].sum() / beginning
                    if beginning and not day_events.empty else 0.0
                ),
                "holdings": len(day_holdings),
            })
            beginning = ending
        return pd.DataFrame(rows)

    @staticmethod
    def _monthly_metrics(daily, monthly_sleeves):
        rows = []
        for month, data in daily.groupby("month"):
            returns = data["daily_return"]
            peak = data["portfolio_value"].cummax()
            row = {
                "month": month,
                "opening_value": data.iloc[0]["portfolio_value"],
                "closing_value": data.iloc[-1]["portfolio_value"],
                "pnl": data.iloc[-1]["portfolio_value"] - data.iloc[0]["portfolio_value"],
                "monthly_return": data.iloc[-1]["portfolio_value"] / data.iloc[0]["portfolio_value"] - 1,
                "max_drawdown": float(-(data["portfolio_value"] / peak - 1).min()),
                "annualized_volatility": float(returns.std(ddof=0) * np.sqrt(252)),
                "sharpe_ratio": (
                    float(returns.mean() / returns.std(ddof=0) * np.sqrt(252))
                    if returns.std(ddof=0) else 0.0
                ),
            }
            sleeve_month = monthly_sleeves[monthly_sleeves["month"] == month]
            row.update({
                "cash_value": sleeve_month["cash"].sum(),
                "stock_value": sleeve_month["stock_value"].sum(),
                "gold_value": sleeve_month["gold_value"].sum(),
            })
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _monthly_return_matrix(monthly):
        data = monthly.copy()
        period = data["month"].astype(str).str.split("-")
        data["year"] = period.str[0].astype(int)
        data["month_number"] = period.str[1].astype(int)
        value_column = "month_return" if "month_return" in data else "period_return"
        matrix = data.pivot(index="year", columns="month_number", values=value_column)
        matrix = matrix.rename(columns={
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
        })
        return matrix.reset_index().rename(columns={"year": "Year"})

    @staticmethod
    def _annual_asset_contribution(sleeve_daily):
        data = sleeve_daily.copy()
        data["year"] = data["date"].dt.year
        data["daily_pnl"] = data.groupby("universe")["total_value"].diff().fillna(0.0)
        data["asset_class"] = np.select(
            [data["gold_value"] > 0, data["stock_value"] > 0],
            ["GOLDBEES", "Stocks"], default="Cash",
        )
        grouped = data.groupby(
            ["year", "universe", "asset_class"], as_index=False
        ).agg(active_days=("date", "size"), pnl=("daily_pnl", "sum"))
        rows = []
        for (year, universe), values in grouped.groupby(["year", "universe"]):
            days = dict(zip(values["asset_class"], values["active_days"]))
            pnl = dict(zip(values["asset_class"], values["pnl"]))
            rows.append({
                "year": year, "universe": universe,
                "stock_days": days.get("Stocks", 0),
                "gold_days": days.get("GOLDBEES", 0),
                "cash_days": days.get("Cash", 0),
                "stock_pnl": pnl.get("Stocks", 0.0),
                "gold_pnl": pnl.get("GOLDBEES", 0.0),
                "cash_pnl": pnl.get("Cash", 0.0),
            })
        result = pd.DataFrame(rows)
        combined = result.groupby("year", as_index=False).agg(
            stock_days=("stock_days", "sum"), gold_days=("gold_days", "sum"),
            cash_days=("cash_days", "sum"), stock_pnl=("stock_pnl", "sum"),
            gold_pnl=("gold_pnl", "sum"), cash_pnl=("cash_pnl", "sum"),
        )
        combined.insert(1, "universe", "COMBINED")
        result = pd.concat([result, combined], ignore_index=True)
        result["total_pnl"] = result[["stock_pnl", "gold_pnl", "cash_pnl"]].sum(axis=1)
        for asset in ("stock", "gold", "cash"):
            result[f"{asset}_pnl_share"] = np.where(
                result["total_pnl"] != 0,
                result[f"{asset}_pnl"] / result["total_pnl"], 0.0,
            )
        return result.sort_values(["year", "universe"])

    @staticmethod
    def _asset_class_performance(sleeve_daily):
        data = sleeve_daily.copy()
        data["daily_return"] = (
            data.groupby("universe")["total_value"]
            .pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
        data["asset_class"] = np.select(
            [data["gold_value"] > 0, data["stock_value"] > 0],
            ["GOLDBEES", "Stocks"], default="Cash",
        )
        grouped = data.groupby(["universe", "asset_class"])["daily_return"]
        rows = []
        for (universe, asset), values in grouped:
            growth = float((1 + values).prod())
            rows.append({
                "universe": universe, "asset_class": asset,
                "active_days": len(values), "total_return": growth - 1,
                "annualized_return": growth ** (252 / len(values)) - 1 if len(values) else 0.0,
            })
        combined = data.groupby("date", as_index=False)["total_value"].sum()
        combined_returns = combined["total_value"].pct_change().fillna(0.0)
        growth = float((1 + combined_returns).prod())
        rows.append({
            "universe": "COMBINED", "asset_class": "Combined",
            "active_days": len(combined_returns), "total_return": growth - 1,
            "annualized_return": (
                growth ** (252 / len(combined_returns)) - 1
                if len(combined_returns) else 0.0
            ),
        })
        return pd.DataFrame(rows)

    @staticmethod
    def _period_report(daily, period):
        report = daily.groupby(period, as_index=False).agg(
            opening_value=("portfolio_value", "first"),
            closing_value=("portfolio_value", "last"),
        )
        report["period_return"] = report["closing_value"] / report["opening_value"] - 1
        report["cumulative_return"] = report["closing_value"] / daily.iloc[0]["portfolio_value"] - 1
        return report

    def _metrics(self, daily):
        initial = float(self.config["initial_capital"])
        final = float(daily.iloc[-1]["portfolio_value"])
        years = max(1 / 252, (daily.iloc[-1]["date"] - daily.iloc[0]["date"]).days / 365.25)
        returns = daily["daily_return"]
        volatility = float(returns.std(ddof=0) * np.sqrt(252))
        sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(252)) if returns.std(ddof=0) else 0.0
        drawdown = daily["portfolio_value"] / daily["portfolio_value"].cummax() - 1
        downside = returns[returns < 0]
        sortino = (
            float(returns.mean() / downside.std(ddof=0) * np.sqrt(252))
            if len(downside) and downside.std(ddof=0) else 0.0
        )
        max_drawdown = float(-drawdown.min())
        cagr = (final / initial) ** (1 / years) - 1
        below_peak = drawdown < 0
        groups = (below_peak != below_peak.shift()).cumsum()
        max_duration = int(below_peak.groupby(groups).sum().max()) if len(daily) else 0
        return {
            "initial_capital": initial,
            "final_portfolio_value": final,
            "total_return": final / initial - 1,
            "cagr": cagr,
            "absolute_return": final / initial - 1,
            "xirr": 0.0,
            "max_drawdown": max_drawdown,
            "max_drawdown_duration": max_duration,
            "annualized_volatility": volatility,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": cagr / max_drawdown if max_drawdown else 0.0,
        }

    def _trade_metrics(self, daily, events, trades):
        initial = float(self.config["initial_capital"])
        if events.empty:
            return {
                key: 0.0 for key in (
                    "total_trades", "winning_trades", "losing_trades", "win_rate",
                    "profit_factor", "expectancy", "average_trade_return",
                    "average_winning_trade", "average_losing_trade",
                    "largest_winning_trade", "largest_losing_trade",
                    "average_holding_days", "median_holding_days", "total_buy_value",
                    "total_sell_value", "portfolio_turnover", "total_buy_transaction_costs",
                    "total_sell_transaction_costs", "total_transaction_costs",
                    "transaction_cost_drag",
                )
            }
        pnl = trades["net_realized_pnl"] if not trades.empty else pd.Series(dtype=float)
        winners, losers = pnl[pnl > 0], pnl[pnl < 0]
        buys = events[events["action"] == "BUY"]
        sells = events[events["action"] == "SELL"]
        total_cost = float(events["transaction_cost"].sum())
        return {
            "total_trades": len(trades),
            "winning_trades": len(winners),
            "losing_trades": len(losers),
            "win_rate": len(winners) / len(trades) if len(trades) else 0.0,
            "profit_factor": winners.sum() / abs(losers.sum()) if len(losers) and losers.sum() else 0.0,
            "expectancy": pnl.mean() if len(pnl) else 0.0,
            "average_trade_return": trades["return_pct"].mean() if len(trades) else 0.0,
            "average_winning_trade": winners.mean() if len(winners) else 0.0,
            "average_losing_trade": losers.mean() if len(losers) else 0.0,
            "largest_winning_trade": winners.max() if len(winners) else 0.0,
            "largest_losing_trade": losers.min() if len(losers) else 0.0,
            "average_holding_days": trades["holding_days"].mean() if len(trades) else 0.0,
            "median_holding_days": trades["holding_days"].median() if len(trades) else 0.0,
            "total_buy_value": buys["gross_value"].sum(),
            "total_sell_value": sells["gross_value"].sum(),
            "portfolio_turnover": (buys["gross_value"].sum() + sells["gross_value"].sum()) / initial,
            "total_buy_transaction_costs": buys["transaction_cost"].sum(),
            "total_sell_transaction_costs": sells["transaction_cost"].sum(),
            "total_transaction_costs": total_cost,
            "transaction_cost_drag": total_cost / initial,
        }
