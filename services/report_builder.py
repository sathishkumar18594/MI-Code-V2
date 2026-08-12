

from models.backtest_result import BacktestResult
from models.report.backtest_report import BacktestReport
from models.report.trade_report import TradeReport
from models.report.holding_report import HoldingReport
from models.report.monthly_report import MonthlyReport
from models.report.summary_report import SummaryReport
from models.report.transaction_cost_report import TransactionCostReport
from models.report.metric_report import MetricReport
from models.report.decision_report import DecisionReport
from models.report.annual_report import AnnualReport
from models.report.stock_summary_report import StockSummaryReport
from models.report.annual_asset_contribution_report import (
    AnnualAssetContributionReport,
)
from models.report.asset_class_performance_report import (
    AssetClassPerformanceReport,
)
from application.app_context import AppContext



class ReportBuilder:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context
        self.config = context.config
        self.report_service = context.report_service

    def build(
        self,
        result: BacktestResult,
    ) -> BacktestReport:

        report = BacktestReport()

        report.summary = self._build_summary(result)
        report.monthly = self._build_monthly(result)
        report.holdings = self._build_holdings(result)
        report.trades = self._build_trades(result)
        report.annual = self._build_annual(result)
        report.transaction_costs = self._build_transaction_costs(result)
        report.metrics = self._build_metrics(result)
        report.decisions = self._build_decisions(result)
        report.stock_summary = self._build_stock_summary(result)
        report.annual_asset_contribution = (
            self._build_annual_asset_contribution(result)
        )
        report.asset_class_performance = (
            self._build_asset_class_performance(result)
        )
        report.monthly_return_matrix = (
            self.report_service.build_monthly_return_matrix(
                result
            )
        )

        return report

    def _build_annual_asset_contribution(self, result):
        """Attribute each daily portfolio P&L to its closing regime.

        A regime is Stocks when any equity is held, Gold when the portfolio is
        fully invested in the configured hedge, and Cash otherwise.  This is
        deliberately based on the same close-to-close daily valuation used by
        the backtest reports.
        """
        hedge_symbol = self.config.get("market_hedge", {}).get(
            "symbol", "GOLDBEES"
        )
        annual = {}

        for period in result.periods:
            portfolio = period.portfolio
            year = portfolio.rebalance_date.year
            row = annual.setdefault(
                year,
                {
                    "year": year,
                    "stock_days": 0,
                    "gold_days": 0,
                    "cash_days": 0,
                    "stock_pnl": 0.0,
                    "gold_pnl": 0.0,
                    "cash_pnl": 0.0,
                },
            )
            symbols = {holding.symbol for holding in portfolio.holdings}
            daily_pnl = (
                period.performance.ending_value
                - period.performance.beginning_value
            )

            if symbols and symbols == {hedge_symbol}:
                row["gold_days"] += 1
                row["gold_pnl"] += daily_pnl
            elif symbols:
                row["stock_days"] += 1
                row["stock_pnl"] += daily_pnl
            else:
                row["cash_days"] += 1
                row["cash_pnl"] += daily_pnl

        reports = []
        for row in annual.values():
            total_pnl = (
                row["stock_pnl"]
                + row["gold_pnl"]
                + row["cash_pnl"]
            )
            reports.append(
                AnnualAssetContributionReport(
                    **row,
                    total_pnl=total_pnl,
                    stock_pnl_share=(
                        row["stock_pnl"] / total_pnl if total_pnl else 0.0
                    ),
                    gold_pnl_share=(
                        row["gold_pnl"] / total_pnl if total_pnl else 0.0
                    ),
                    cash_pnl_share=(
                        row["cash_pnl"] / total_pnl if total_pnl else 0.0
                    ),
                )
            )

        return sorted(reports, key=lambda report: report.year)

    def _build_asset_class_performance(self, result):
        """Return conditional performance for stocks, gold, and the whole strategy."""
        hedge_symbol = self.config.get("market_hedge", {}).get(
            "symbol", "GOLDBEES"
        )
        returns = {"Stocks": [], "GOLDBEES": [], "Combined": []}

        for period in result.periods:
            daily_return = period.performance.period_return
            returns["Combined"].append(daily_return)
            symbols = {holding.symbol for holding in period.portfolio.holdings}
            if symbols == {hedge_symbol}:
                returns["GOLDBEES"].append(daily_return)
            elif symbols:
                returns["Stocks"].append(daily_return)

        reports = []
        for asset_class, daily_returns in returns.items():
            active_days = len(daily_returns)
            growth = 1.0
            for daily_return in daily_returns:
                growth *= 1.0 + daily_return
            total_return = growth - 1.0
            active_years = active_days / 252
            cagr = (
                growth ** (1.0 / active_years) - 1.0
                if active_years and growth > 0 else 0.0
            )
            reports.append(
                AssetClassPerformanceReport(
                    asset_class=asset_class,
                    active_trading_days=active_days,
                    active_years=active_years,
                    total_return=total_return,
                    cagr=cagr,
                )
            )

        return reports

    def _build_stock_summary(self, result):
        closed_trades = {}
        for period in result.periods:
            for trade in period.portfolio.trades:
                closed_trades[(trade.symbol, trade.entry_date, trade.exit_date)] = trade

        summaries = {}
        for trade in closed_trades.values():
            summary = summaries.setdefault(trade.symbol, self._empty_stock_summary(trade.symbol))
            summary["closed_invested_amount"] += trade.cost_value
            summary["realized_pnl"] += trade.net_realized_pnl
            summary["total_transaction_cost"] += trade.total_charges
            summary["closed_trades"] += 1
            if trade.net_realized_pnl > 0:
                summary["winning_trades"] += 1
            elif trade.net_realized_pnl < 0:
                summary["losing_trades"] += 1

        if result.periods:
            for holding in result.periods[-1].portfolio.holdings:
                summary = summaries.setdefault(
                    holding.symbol, self._empty_stock_summary(holding.symbol)
                )
                summary["open_invested_amount"] += holding.cost_value
                summary["open_market_value"] += holding.market_value
                summary["unrealized_pnl"] += holding.market_value - holding.cost_value

        reports = []
        for summary in summaries.values():
            summary["total_invested_amount"] = (
                summary["closed_invested_amount"] + summary["open_invested_amount"]
            )
            summary["total_pnl"] = summary["realized_pnl"] + summary["unrealized_pnl"]
            summary["total_return_pct"] = (
                summary["total_pnl"] / summary["total_invested_amount"]
                if summary["total_invested_amount"] else 0.0
            )
            reports.append(StockSummaryReport(**summary))

        return sorted(reports, key=lambda report: report.total_pnl, reverse=True)

    @staticmethod
    def _empty_stock_summary(symbol):
        return {
            "symbol": symbol,
            "total_invested_amount": 0.0,
            "closed_invested_amount": 0.0,
            "open_invested_amount": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0,
            "total_return_pct": 0.0,
            "closed_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_transaction_cost": 0.0,
            "open_market_value": 0.0,
        }

    def _build_summary(self, result):

        if not result.periods:
            return None

        first_portfolio = result.periods[0].portfolio
        last_portfolio = result.periods[-1].portfolio

        initial_capital = getattr(
            first_portfolio,
            "initial_capital",
            last_portfolio.total_value,
        )

        final_value = result.periods[-1].performance.ending_value

        absolute_return = (
            (final_value - initial_capital)
            / initial_capital
            if initial_capital > 0
            else 0.0
        )

        metrics = result.metrics

        strategy = self.config["strategy"]
        universe_name = self.config["universe"]["name"]

        return SummaryReport(
            strategy_name=strategy.get("name", "Momentum V1"),
            benchmark_name=strategy.get("benchmark", universe_name),
            universe=strategy.get("universe", universe_name),
            portfolio_size=strategy.get(
                "portfolio_size",
                len(first_portfolio.holdings),
            ),
            rebalance_frequency=strategy.get(
                "rebalance_frequency",
                "Monthly",
            ),
            market_filter=strategy.get(
                "market_filter",
                "Weekly Supertrend",
            ),
            initial_capital=initial_capital,
            final_portfolio_value=final_value,
            absolute_return=absolute_return,
            cagr=getattr(metrics, "cagr", 0.0),
            xirr=getattr(metrics, "xirr", 0.0),
            max_drawdown=getattr(metrics, "max_drawdown", 0.0),
            sharpe_ratio=getattr(metrics, "sharpe_ratio", 0.0),
            sortino_ratio=getattr(metrics, "sortino_ratio", 0.0),
            calmar_ratio=getattr(metrics, "calmar_ratio", 0.0),
            total_trades=getattr(metrics, "total_trades", 0),
            winning_trades=getattr(metrics, "winning_trades", 0),
            losing_trades=getattr(metrics, "losing_trades", 0),
            win_rate=getattr(metrics, "win_rate", 0.0),
            profit_factor=getattr(metrics, "profit_factor", 0.0),
            average_holding_days=getattr(metrics, "average_holding_days", 0.0),
            portfolio_turnover=getattr(metrics, "portfolio_turnover", 0.0),
            total_transaction_costs=getattr(metrics, "total_transaction_costs", 0.0),
        )

    def _build_monthly(self, result):

        reports = []

        # This file is the daily portfolio timeline used to audit rank exits.
        # The separate monthly_return_matrix contains the compounded monthly
        # performance figures.
        for period in result.periods:
            portfolio = period.portfolio
            performance = period.performance

            reports.append(
                MonthlyReport(
                    rebalance_date=portfolio.rebalance_date,
                    beginning_value=performance.beginning_value,
                    ending_value=performance.ending_value,
                    monthly_return=performance.period_return,
                    cash=portfolio.cash,
                    invested_value=portfolio.invested_value,
                    realized_pnl=performance.period_realized_pnl,
                    unrealized_pnl=performance.period_unrealized_pnl,
                    buy_value=portfolio.buy_value,
                    sell_value=portfolio.sell_value,
                    buy_transaction_costs=portfolio.buy_transaction_costs,
                    sell_transaction_costs=portfolio.sell_transaction_costs,
                    transaction_costs=portfolio.transaction_costs,
                    turnover=portfolio.turnover,
                    holdings=len(portfolio.holdings),
                )
            )

        return reports

    def _build_holdings(self, result):

        holdings = []

        # Keep daily snapshots: rank exits can occur every trading day, while
        # new positions are only filled on the monthly rebalance.
        for period in result.periods:

            for holding in period.portfolio.holdings:

                unrealized_return = (
                    holding.unrealized_pnl
                    / holding.cost_value
                    if holding.cost_value > 0
                    else 0.0
                )

                holdings.append(
                    HoldingReport(
                        rebalance_date=period.portfolio.rebalance_date,
                        symbol=holding.symbol,
                        rank=holding.rank,
                        score=holding.score,
                        weight=holding.weight,
                        quantity=holding.quantity,
                        entry_date=holding.entry_date,
                        entry_price=holding.entry_price,
                        current_price=holding.current_price,
                        cost_value=holding.cost_value,
                        market_value=holding.market_value,
                        unrealized_pnl=holding.unrealized_pnl,
                        unrealized_return_pct=unrealized_return,
                        holding_days=(
                            period.portfolio.rebalance_date
                            - holding.entry_date
                        ).days,
                    )
                )

        return holdings

    def _build_trades(self, result):

        trades = []
        processed = set()

        for period in result.periods:

            for trade in period.portfolio.trades:
                key = (
                    trade.symbol,
                    trade.entry_date,
                    trade.exit_date,
                )

                if key in processed:
                    continue

                processed.add(key)

                trades.append(
                    TradeReport(
                        symbol=trade.symbol,
                        entry_date=trade.entry_date,
                        entry_rank=trade.entry_rank,
                        exit_date=trade.exit_date,
                        exit_rank=trade.exit_rank,
                        holding_days=trade.holding_days,
                        quantity=trade.quantity,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        cost_value=trade.cost_value,
                        proceeds=trade.proceeds,
                        gross_realized_pnl=trade.gross_realized_pnl,
                        brokerage=trade.brokerage,
                        stt=trade.stt,
                        exchange_charge=trade.exchange_charge,
                        sebi_charge=trade.sebi_charge,
                        gst=trade.gst,
                        stamp_duty=trade.stamp_duty,
                        total_transaction_cost=trade.total_charges,
                        net_realized_pnl=trade.net_realized_pnl,
                        return_pct=trade.return_pct,
                        sell_reason=trade.sell_reason,
                    )
                )

        return trades

    def _build_annual(self, result):

        yearly = {}

        for period in result.periods:
            year = period.portfolio.rebalance_date.year
            if year not in yearly:
                yearly[year] = []
            yearly[year].append(period)

        reports = []

        for year in sorted(yearly):

            periods = yearly[year]

            first = periods[0].portfolio
            last = periods[-1].portfolio

            beginning_value = periods[0].performance.beginning_value
            ending_value = periods[-1].performance.ending_value

            annual_return = (
                (ending_value - beginning_value)
                / beginning_value
                if beginning_value > 0
                else 0.0
            )

            trades = []
            winning = 0
            losing = 0
            gross_profit = 0.0
            gross_loss = 0.0

            processed = set()

            for period in periods:
                for trade in period.portfolio.trades:
                    key = (
                        trade.symbol,
                        trade.entry_date,
                        trade.exit_date,
                    )

                    if key in processed:
                        continue

                    processed.add(key)
                    trades.append(trade)

                    if trade.net_realized_pnl >= 0:
                        winning += 1
                        gross_profit += trade.net_realized_pnl
                    else:
                        losing += 1
                        gross_loss += abs(trade.net_realized_pnl)

            trade_count = len(trades)

            # Annual performance is the aggregation of period performance,
            # not a recomputation from the portfolio snapshots.
            annual_realized_pnl = sum(trade.net_realized_pnl for trade in trades)
            annual_unrealized_pnl = periods[-1].performance.unrealized_pnl
            buy_value = sum(trade.cost_value for trade in trades)
            sell_value = sum(trade.proceeds for trade in trades)
            buy_costs = sum(
                max(0.0, trade.cost_value - trade.quantity * trade.entry_price)
                for trade in trades
            )
            sell_costs = sum(trade.total_charges for trade in trades)
            returns = [period.performance.period_return for period in periods]

            reports.append(
                AnnualReport(
                    year=year,
                    beginning_value=beginning_value,
                    ending_value=ending_value,
                    annual_return=annual_return,
                    realized_pnl=annual_realized_pnl,
                    unrealized_pnl=annual_unrealized_pnl,
                    buy_value=buy_value,
                    sell_value=sell_value,
                    turnover=(
                        (buy_value + sell_value) / beginning_value
                        if beginning_value else 0.0
                    ),
                    buy_transaction_costs=buy_costs,
                    sell_transaction_costs=sell_costs,
                    transaction_costs=buy_costs + sell_costs,
                    trades=trade_count,
                    winning_trades=winning,
                    losing_trades=losing,
                    win_rate=(winning / trade_count if trade_count else 0.0),
                    profit_factor=(gross_profit / gross_loss if gross_loss > 0 else 0.0),
                    max_drawdown=self._max_drawdown(returns),
                )
            )

        return reports

    @staticmethod
    def _max_drawdown(returns):
        equity = peak = 1.0
        drawdown = 0.0
        for value in returns:
            equity *= 1 + value
            peak = max(peak, equity)
            drawdown = min(drawdown, (equity - peak) / peak)
        return abs(drawdown)

    def _build_transaction_costs(self, result):

        reports = []

        for period in result.periods:

            portfolio = period.portfolio

            total_value = (
                portfolio.buy_value
                + portfolio.sell_value
            )

            transaction_cost_pct = (
                portfolio.transaction_costs
                / total_value
                if total_value > 0
                else 0.0
            )

            reports.append(
                TransactionCostReport(
                    rebalance_date=portfolio.rebalance_date,
                    buy_value=portfolio.buy_value,
                    sell_value=portfolio.sell_value,
                    brokerage=0.0,
                    stt=0.0,
                    exchange_charge=0.0,
                    sebi_charge=0.0,
                    gst=0.0,
                    stamp_duty=0.0,
                    total_transaction_cost=portfolio.transaction_costs,
                    transaction_cost_pct=transaction_cost_pct,
                )
            )

        return reports

    def _build_metrics(self, result):

        metrics = result.metrics

        if metrics is None:
            return None

        return MetricReport(
            initial_capital=getattr(metrics, "initial_capital", 0.0),
            final_portfolio_value=getattr(metrics, "final_portfolio_value", 0.0),
            absolute_return=getattr(metrics, "absolute_return", 0.0),
            cagr=getattr(metrics, "cagr", 0.0),
            xirr=getattr(metrics, "xirr", 0.0),
            annualized_volatility=getattr(metrics, "annualized_volatility", 0.0),
            sharpe_ratio=getattr(metrics, "sharpe_ratio", 0.0),
            sortino_ratio=getattr(metrics, "sortino_ratio", 0.0),
            calmar_ratio=getattr(metrics, "calmar_ratio", 0.0),
            max_drawdown=getattr(metrics, "max_drawdown", 0.0),
            max_drawdown_duration=getattr(metrics, "max_drawdown_duration", 0),
            total_trades=getattr(metrics, "total_trades", 0),
            winning_trades=getattr(metrics, "winning_trades", 0),
            losing_trades=getattr(metrics, "losing_trades", 0),
            win_rate=getattr(metrics, "win_rate", 0.0),
            profit_factor=getattr(metrics, "profit_factor", 0.0),
            expectancy=getattr(metrics, "expectancy", 0.0),
            average_trade_return=getattr(metrics, "average_trade_return", 0.0),
            average_winning_trade=getattr(metrics, "average_winning_trade", 0.0),
            average_losing_trade=getattr(metrics, "average_losing_trade", 0.0),
            largest_winning_trade=getattr(metrics, "largest_winning_trade", 0.0),
            largest_losing_trade=getattr(metrics, "largest_losing_trade", 0.0),
            average_holding_days=getattr(metrics, "average_holding_days", 0.0),
            median_holding_days=getattr(metrics, "median_holding_days", 0.0),
            total_buy_value=getattr(metrics, "total_buy_value", 0.0),
            total_sell_value=getattr(metrics, "total_sell_value", 0.0),
            portfolio_turnover=getattr(metrics, "portfolio_turnover", 0.0),
            total_buy_transaction_costs=getattr(metrics, "total_buy_transaction_costs", 0.0),
            total_sell_transaction_costs=getattr(metrics, "total_sell_transaction_costs", 0.0),
            total_transaction_costs=getattr(metrics, "total_transaction_costs", 0.0),
            transaction_cost_drag=getattr(metrics, "transaction_cost_drag", 0.0),
        )

    def _build_decisions(self, result):

        decisions = []

        processed = set()

        for period in result.periods:

            portfolio = period.portfolio

            for trade in portfolio.trades:

                key = (
                    trade.symbol,
                    trade.entry_date,
                    trade.exit_date,
                )

                if key in processed:
                    continue

                processed.add(key)

                decisions.append(
                    DecisionReport(
                        rebalance_date=portfolio.rebalance_date,
                        decision_date=trade.exit_date,
                        action="SELL",
                        symbol=trade.symbol,
                        reason=trade.sell_reason,
                        quantity=trade.quantity,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        trade_value=trade.proceeds,
                        transaction_cost=trade.total_charges,
                        portfolio_value=portfolio.total_value,
                        cash_after=portfolio.cash,
                        notes="",
                    )
                )

            for holding in portfolio.holdings:

                if holding.entry_date != portfolio.rebalance_date:
                    continue

                decisions.append(
                    DecisionReport(
                        rebalance_date=portfolio.rebalance_date,
                        decision_date=portfolio.rebalance_date,
                        action="BUY",
                        symbol=holding.symbol,
                        reason="NEW_POSITION",
                        rank_after=holding.rank,
                        score=holding.score,
                        weight_after=holding.weight,
                        quantity=holding.quantity,
                        entry_price=holding.entry_price,
                        trade_value=holding.cost_value,
                        transaction_cost=(
                            holding.cost_value
                            - (holding.quantity * holding.entry_price)
                        ),
                        portfolio_value=portfolio.total_value,
                        cash_after=portfolio.cash,
                        notes="",
                    )
                )

        return decisions
