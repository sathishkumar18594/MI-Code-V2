import math
import statistics

from models.backtest_metrics import (
    BacktestMetrics,
)
from models.backtest_result import (
    BacktestResult,
)


class MetricsService:

    def calculate(
        self,
        result: BacktestResult,
    ) -> BacktestMetrics:

        returns = [
            getattr(
                period.performance,
                "period_return",
                getattr(period.performance, "portfolio_return", 0.0),
            )
            for period in result.periods
        ]

        if not returns:

            return BacktestMetrics()

        metrics = BacktestMetrics()

        first_period = result.periods[0]
        last_period = result.periods[-1]
        metrics.initial_capital = first_period.performance.beginning_value
        metrics.final_portfolio_value = last_period.performance.ending_value
        metrics.absolute_return = (
            (metrics.final_portfolio_value - metrics.initial_capital)
            / metrics.initial_capital
            if metrics.initial_capital else 0.0
        )

        # Determine the effective number of periods per year.
        periods_per_year = 252

        if len(result.periods) >= 2:

            start_date = (
                result.periods[0]
                .portfolio
                .rebalance_date
            )

            end_date = (
                result.periods[-1]
                .portfolio
                .rebalance_date
            )

            total_days = max(
                1,
                (end_date - start_date).days,
            )

            years = (
                total_days
                / 365.25
            )

            if years > 0:
                periods_per_year = (
                    len(returns)
                    / years
                )

        metrics.total_return = (
            self.total_return(
                returns
            )
        )

        metrics.cagr = self.cagr(
            returns,
            periods_per_year,
        )

        metrics.max_drawdown = (
            self.max_drawdown(
                returns
            )
        )

        metrics.win_rate = (
            self.win_rate(
                returns
            )
        )

        metrics.annualized_volatility = (
            statistics.stdev(returns) * math.sqrt(periods_per_year)
            if len(returns) > 1 else 0.0
        )
        downside = [value for value in returns if value < 0]
        if downside:
            downside_deviation = math.sqrt(
                sum(value ** 2 for value in downside) / len(downside)
            )
            metrics.sortino_ratio = (
                (sum(returns) / len(returns)) / downside_deviation
                * math.sqrt(periods_per_year)
                if downside_deviation else 0.0
            )
        metrics.calmar_ratio = (
            metrics.cagr / metrics.max_drawdown
            if metrics.max_drawdown else 0.0
        )
        metrics.max_drawdown_duration = self.max_drawdown_duration(returns)

        trades = self.unique_trades(result)
        pnl = [trade.net_realized_pnl for trade in trades]
        winners = [value for value in pnl if value > 0]
        losers = [value for value in pnl if value < 0]
        metrics.total_trades = len(trades)
        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        metrics.win_rate = len(winners) / len(trades) if trades else 0.0
        metrics.profit_factor = (
            sum(winners) / abs(sum(losers)) if losers else 0.0
        )
        metrics.expectancy = sum(pnl) / len(pnl) if pnl else 0.0
        returns_by_trade = [trade.return_pct for trade in trades]
        metrics.average_trade_return = (
            sum(returns_by_trade) / len(returns_by_trade)
            if returns_by_trade else 0.0
        )
        metrics.average_winning_trade = sum(winners) / len(winners) if winners else 0.0
        metrics.average_losing_trade = sum(losers) / len(losers) if losers else 0.0
        metrics.largest_winning_trade = max(winners) if winners else 0.0
        metrics.largest_losing_trade = min(losers) if losers else 0.0
        holding_days = [trade.holding_days for trade in trades]
        metrics.average_holding_days = (
            sum(holding_days) / len(holding_days) if holding_days else 0.0
        )
        metrics.median_holding_days = statistics.median(holding_days) if holding_days else 0.0
        metrics.total_buy_value = sum(trade.cost_value for trade in trades)
        metrics.total_sell_value = sum(trade.proceeds for trade in trades)
        open_holdings = last_period.portfolio.holdings
        metrics.total_buy_value += sum(
            holding.cost_value for holding in open_holdings
        )
        metrics.total_buy_transaction_costs = sum(
            max(0.0, trade.cost_value - trade.quantity * trade.entry_price)
            for trade in trades
        ) + sum(
            max(0.0, holding.cost_value - holding.quantity * holding.entry_price)
            for holding in open_holdings
        )
        metrics.portfolio_turnover = (
            (metrics.total_buy_value + metrics.total_sell_value)
            / metrics.initial_capital if metrics.initial_capital else 0.0
        )
        metrics.total_sell_transaction_costs = sum(
            trade.total_charges for trade in trades
        )
        metrics.total_transaction_costs = (
            metrics.total_buy_transaction_costs
            + metrics.total_sell_transaction_costs
        )
        metrics.transaction_cost_drag = (
            metrics.total_transaction_costs / metrics.initial_capital
            if metrics.initial_capital else 0.0
        )

        metrics.sharpe_ratio = (
            self.sharpe_ratio(
                returns,
                periods_per_year,
            )
        )

        metrics.annual_return = (
            metrics.cagr
        )

        return metrics

    def unique_trades(self, result):
        trades = {}
        for period in result.periods:
            for trade in period.portfolio.trades:
                key = (trade.symbol, trade.entry_date, trade.exit_date)
                trades[key] = trade
        return list(trades.values())

    def max_drawdown_duration(self, returns):
        equity = peak = 1.0
        duration = longest = 0
        for value in returns:
            equity *= 1 + value
            if equity >= peak:
                peak = equity
                duration = 0
            else:
                duration += 1
                longest = max(longest, duration)
        return longest

    def total_return(
        self,
        returns,
    ):

        equity = 1.0

        for value in returns:

            equity *= (
                1 + value
            )

        return equity - 1

    def cagr(
        self,
        returns,
        periods_per_year,
    ):

        years = (
            len(returns)
            / periods_per_year
        )

        if years == 0:

            return 0.0

        total = (
            self.total_return(
                returns
            )
        )

        return (
            (1 + total)
            ** (1 / years)
            - 1
        )

    def max_drawdown(
        self,
        returns,
    ):

        equity = 1.0

        peak = 1.0

        drawdown = 0.0

        for value in returns:

            equity *= (
                1 + value
            )

            peak = max(
                peak,
                equity,
            )

            drawdown = min(
                drawdown,
                (
                    equity
                    - peak
                )
                / peak,
            )

        return abs(
            drawdown
        )

    def win_rate(
        self,
        returns,
    ):

        wins = sum(
            1
            for value in returns
            if value > 0
        )

        return (
            wins
            / len(returns)
        )

    def sharpe_ratio(
        self,
        returns,
        periods_per_year,
        risk_free=0.0,
    ):

        if len(
            returns
        ) < 2:

            return 0.0

        average = (
            sum(returns)
            / len(returns)
        )

        variance = sum(

            (
                value
                - average
            ) ** 2

            for value in returns

        ) / (
            len(returns) - 1
        )

        std = math.sqrt(
            variance
        )

        if std == 0:

            return 0.0

        return (
            (
                average
                - risk_free
            )
            / std
        ) * math.sqrt(
            periods_per_year
        )
