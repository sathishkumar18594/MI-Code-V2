"""Standalone breadth-rotation strategy; it does not modify existing engines."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from models.portfolio_sleeve import PortfolioSleeve
from services.multi_universe_backtest_service import MultiUniverseBacktestService
from services.multi_universe_data_service import MultiUniverseDataService
from services.multi_universe_portfolio_manager import MultiUniversePortfolioManager


class RotationBacktestService(MultiUniverseBacktestService):
    """Own one equity sleeve and rotate it to the broadest bullish universe."""

    def __init__(self, context):
        self.context = context
        config_file = Path(os.getenv(
            "ROTATION_CONFIG",
            "config/universe_rotation.yaml",
        ))
        self.config = yaml.safe_load(config_file.read_text())
        self.priority = list(self.config["rotation_priority"])
        data_config = {
            "sleeves": [
                {
                    "universe": universe,
                    "index_symbol": self._index_symbol(universe),
                    "capital": self.config["initial_capital"],
                    "portfolio_size": self.config["portfolio_size"],
                }
                for universe in self.priority
            ]
        }
        self.data = MultiUniverseDataService(context, data_config)
        self.manager = MultiUniversePortfolioManager(context, self.config)

    @staticmethod
    def _index_symbol(universe):
        return {
            "NIFTY50": "^NSEI",
            "NIFTY100": "^CNX100",
            "NIFTY200": "^CNX200",
            "NIFTY500": "^CRSLDX",
        }[universe]

    def active_universe(self, signal_date):
        """Return the first bullish universe, or None when all are bearish."""
        return next(
            (
                universe
                for universe in self.priority
                if self.data.is_bullish(universe, signal_date)
            ),
            None,
        )

    def run(
        self,
        trading_dates,
        rebalance_dates,
        output_directory="reports/universe_rotation",
    ):
        dates = [pd.Timestamp(date).normalize() for date in trading_dates]
        signal_dates = {pd.Timestamp(date).normalize() for date in rebalance_dates}
        date_index = {date: index for index, date in enumerate(dates)}
        rebalance_execution_dates = {
            dates[date_index[signal] + 1]
            for signal in signal_dates
            if signal in date_index and date_index[signal] + 1 < len(dates)
        }

        self.manager.events = []
        self.data.build(dates)
        initial = float(self.config["initial_capital"])
        sleeve = PortfolioSleeve(
            universe="DEFENSIVE",
            capital=initial,
            portfolio_size=int(self.config["portfolio_size"]),
            cash=initial,
        )
        current_universe = None
        allocation_initialized = False
        daily_rows, sleeve_rows, holding_rows = [], [], []
        ranking_rows, circuit_rows, regime_rows = [], [], []

        for index in range(1, len(dates)):
            date = dates[index]
            signal_date = dates[index - 1]
            selected_universe = self.active_universe(signal_date)
            regime_changed = (
                not allocation_initialized
                or selected_universe != current_universe
            )
            self.manager.decision_date = signal_date

            if regime_changed:
                previous = (
                    current_universe or "DEFENSIVE"
                    if allocation_initialized else "UNALLOCATED"
                )
                if sleeve.holdings:
                    self.manager.liquidate(sleeve, date, "REGIME_ROTATION")
                current_universe = selected_universe
                allocation_initialized = True
                sleeve.universe = current_universe or "DEFENSIVE"
                regime_rows.append({
                    "signal_date": signal_date,
                    "execution_date": date,
                    "from_universe": previous,
                    "to_universe": sleeve.universe,
                    **{
                        f"{universe.lower()}_bullish": self.data.is_bullish(
                            universe, signal_date
                        )
                        for universe in self.priority
                    },
                })

            if current_universe is None:
                if self.manager.hedge_enabled:
                    if not self.manager._is_hedged(sleeve):
                        self.manager.buy_hedge(sleeve, date)
                    else:
                        self.manager.mark_to_market(sleeve, date)
                else:
                    self.manager.mark_to_market(sleeve, date)
            else:
                rankings = self.data.rankings(current_universe, signal_date)
                entry_rankings = self.data.rankings(
                    current_universe, signal_date, entry=True
                )
                should_rebalance = (
                    regime_changed
                    or date in rebalance_execution_dates
                )
                self.manager.update_sleeve(
                    sleeve=sleeve,
                    market_bullish=True,
                    rankings=rankings,
                    entry_rankings=entry_rankings,
                    date=date,
                    is_rebalance_day=should_rebalance,
                    reserved_symbols=set(),
                    signal_date=signal_date,
                )
                if should_rebalance:
                    selected = {item.symbol for item in sleeve.holdings}
                    eligible = {item.stock.symbol for item in entry_rankings}
                    for ranking in rankings:
                        symbol = ranking.stock.symbol
                        status = (
                            "SELECTED" if symbol in selected else
                            "ELIGIBLE" if symbol in eligible else
                            "ENTRY_FILTERED"
                        )
                        ranking_rows.append({
                            "date": signal_date,
                            "execution_date": date,
                            "universe": current_universe,
                            "rank": ranking.rank,
                            "symbol": symbol,
                            "score": ranking.score,
                            **ranking.factor_values,
                            "status": status,
                        })
                        if symbol not in eligible:
                            risk = self.data.circuit_risk(
                                current_universe, symbol, signal_date
                            )
                            circuit_hit = (
                                risk.get("max_lower_circuit_streak", 0)
                                >= risk.get("filter_threshold", float("inf"))
                            )
                            circuit_rows.append({
                                "date": signal_date,
                                "execution_date": date,
                                "universe": current_universe,
                                "symbol": symbol,
                                "rank": ranking.rank,
                                "reason": (
                                    "LOWER_CIRCUIT_FILTER" if circuit_hit
                                    else "MARKET_CAP_FILTER"
                                ),
                                **risk,
                            })

            for item in sleeve.holdings:
                holding_rows.append({
                    "date": date,
                    "universe": sleeve.universe,
                    "symbol": item.symbol,
                    "rank": item.rank,
                    "score": item.score,
                    "entry_date": item.entry_date,
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
            stock_value = sum(
                item.market_value for item in sleeve.holdings
                if item.symbol != self.manager.hedge_symbol
            )
            gold_value = sum(
                item.market_value for item in sleeve.holdings
                if item.symbol == self.manager.hedge_symbol
            )
            sleeve_rows.append({
                "date": date,
                "universe": "ROTATION",
                "active_universe": sleeve.universe,
                "cash": sleeve.cash,
                "stock_value": stock_value,
                "gold_value": gold_value,
                "total_value": sleeve.value,
                "holdings": ",".join(item.symbol for item in sleeve.holdings),
            })
            daily_rows.append({
                "date": date,
                "portfolio_value": sleeve.value,
            })

        return self._write_rotation_reports(
            daily_rows=daily_rows,
            sleeve_rows=sleeve_rows,
            holding_rows=holding_rows,
            ranking_rows=ranking_rows,
            circuit_rows=circuit_rows,
            regime_rows=regime_rows,
            output_directory=output_directory,
        )

    def _write_rotation_reports(
        self,
        daily_rows,
        sleeve_rows,
        holding_rows,
        ranking_rows,
        circuit_rows,
        regime_rows,
        output_directory,
    ):
        daily = pd.DataFrame(daily_rows)
        daily["daily_return"] = daily["portfolio_value"].pct_change().fillna(0.0)
        daily["month"] = daily["date"].dt.to_period("M")
        daily["year"] = daily["date"].dt.year
        sleeve_daily = pd.DataFrame(sleeve_rows)
        sleeve_daily["month"] = sleeve_daily["date"].dt.to_period("M")
        sleeve_daily["year"] = sleeve_daily["date"].dt.year
        holdings = pd.DataFrame(holding_rows)
        if not holdings.empty:
            total = holdings.groupby("date")["market_value"].transform("sum")
            holdings["weight"] = np.where(
                total > 0, holdings["market_value"] / total, 0.0
            )
            holdings.insert(0, "rebalance_date", holdings["date"])

        events = pd.DataFrame(self.manager.events)
        trades = self._trades_report(events)
        metrics = self._metrics(daily)
        metrics.update(self._trade_metrics(daily, events, trades))
        monthly_sleeves = (
            sleeve_daily.groupby(["month", "universe"], as_index=False)
            .last()[[
                "month", "universe", "cash", "stock_value",
                "gold_value", "total_value",
            ]]
        )
        monthly_summary = self._period_details(
            daily, sleeve_daily, holdings, events, trades, "month"
        )
        monthly_risk = self._monthly_metrics(daily, monthly_sleeves)
        monthly_metrics = monthly_summary.merge(
            monthly_risk[[
                "month", "annualized_volatility", "sharpe_ratio",
                "cash_value", "stock_value", "gold_value",
            ]],
            on="month",
            how="left",
        )
        monthly = self._daily_accounting(
            daily, sleeve_daily, holdings, events, trades
        )
        annual = self._period_details(
            daily, sleeve_daily, holdings, events, trades, "year"
        )
        rankings = pd.DataFrame(ranking_rows)
        circuit = pd.DataFrame(circuit_rows)
        lower_circuit = (
            circuit[circuit["reason"] == "LOWER_CIRCUIT_FILTER"].copy()
            if not circuit.empty else circuit.copy()
        )
        decisions = events.copy()
        transaction_costs = self._transaction_cost_report(events)
        stock_summary = self._stock_summary(trades, holdings)
        annual_asset = self._annual_asset_contribution(sleeve_daily)
        asset_performance = self._asset_class_performance(sleeve_daily)
        summary = pd.DataFrame([{
            **metrics,
            "strategy_name": self.config.get(
                "strategy_name", "Breadth Rotation Momentum"
            ),
            "universe": ">".join(self.priority),
            "portfolio_size": int(self.config["portfolio_size"]),
            "rebalance_frequency": "Monthly and regime change",
            "market_filter": "Weekly Supertrend (1, 2.5)",
        }])

        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        reports = {
            "daily_portfolio.csv": daily,
            "sleeve_daily.csv": sleeve_daily,
            "monthly.csv": monthly,
            "annual.csv": annual,
            "monthly_metrics.csv": monthly_metrics,
            "monthly_return_matrix.csv": self._monthly_return_matrix(
                monthly_summary
            ),
            "metrics.csv": pd.DataFrame([metrics]),
            "summary.csv": summary,
            "holdings.csv": holdings,
            "trades.csv": trades,
            "decisions.csv": decisions,
            "rankings.csv": rankings,
            "circuit_screen.csv": circuit,
            "lower_circuit_filtered_stocks.csv": lower_circuit,
            "transaction_costs.csv": transaction_costs,
            "stock_summary.csv": stock_summary,
            "annual_asset_contribution.csv": annual_asset,
            "asset_class_performance.csv": asset_performance,
            "regime_rotations.csv": pd.DataFrame(regime_rows),
        }
        for filename, report in reports.items():
            report.to_csv(output / filename, index=False)
        return {
            "daily": daily,
            "sleeves": sleeve_daily,
            "metrics": metrics,
        }
