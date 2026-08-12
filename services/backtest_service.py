from copy import deepcopy
from models.backtest_period import (
    BacktestPeriod,
)
from models.backtest_result import (
    BacktestResult,
)
from models.portfolio_state import (
    PortfolioState,
)
from services.market_filter_service import (
    MarketFilterService,
)
from services.performance_service import (
    PerformanceService,
)
from services.metrics_service import (
    MetricsService,
)
from services.report_builder import (
    ReportBuilder,
)
from reports.csv_report_writer import (
    CsvReportWriter,
)
from services.portfolio_manager import (
    PortfolioManager,
)
from services.ranking_service import (
    RankingService,
)
from services.universe_service import UniverseService
from application.app_context import AppContext


class BacktestService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        self.market_filter = (
            MarketFilterService(
                context
            )
        )

        self.ranking_service = (
            RankingService(
                context
            )
        )
        self.portfolio_manager = (
            PortfolioManager(
                context
            )
        )

        self.performance_service = (
            PerformanceService(
                context
            )
        )

        self.metrics_service = (
            MetricsService()
        )

        self.report_builder = (
            ReportBuilder(
                context
            )
        )

        self.csv_report_writer = (
            CsvReportWriter(
                context
            )
        )

    def run(
        self,
        symbols,
        trading_dates,
        rebalance_dates,
        write_reports=True,
    ) -> BacktestResult:

        periods = []

        state = PortfolioState(
            cash=self.context.config["portfolio"]["initial_capital"],
        )
        previous_ending_value = (
            self.context.config["portfolio"]["initial_capital"]
        )
        rebalance_execution_dates = set()
        trading_date_index = {
            date: index for index, date in enumerate(trading_dates)
        }
        for signal_date in rebalance_dates:
            index = trading_date_index.get(signal_date)
            if index is not None and index + 1 < len(trading_dates):
                rebalance_execution_dates.add(trading_dates[index + 1])
        universe_service = UniverseService()
        universe_name = self.context.config["universe"]["name"].lower()
        history_file = universe_service.history_file(universe_name)
        try:
            symbols_by_date = {
                date: universe_service.get_universe_as_of(universe_name, date)
                for date in trading_dates
            }
            cache_symbols = universe_service.history_symbols(
                universe_name,
                trading_dates[0],
                trading_dates[-1],
            )
        except ValueError:
            # A malformed or incomplete imported ledger must not quietly turn
            # a historical backtest into a present-day-universe backtest.
            if history_file.exists():
                raise
            # Retain current behavior until a historical ledger is imported.
            symbols_by_date = None
            cache_symbols = symbols

        self.ranking_service.build_cache(
            symbols=cache_symbols,
            trading_dates=trading_dates,
            symbols_by_date=symbols_by_date,
        )
        for index in range(1, len(trading_dates)):

            trading_date = trading_dates[index]
            signal_date = trading_dates[index - 1]

            state, period, previous_ending_value = (
                self.execute_day(
                    state=state,
                    trading_date=trading_date,
                    exit_date=trading_date,
                    previous_ending_value=previous_ending_value,
                    signal_date=signal_date,
                    is_rebalance_day=(trading_date in rebalance_execution_dates),
                )
            )

            periods.append(period)

        result = BacktestResult(
            periods=periods,
            metrics=None,
        )

        result.metrics = (
            self.metrics_service.calculate(
                result
            )
        )

        if write_reports:
            report = self.report_builder.build(result)
            self.csv_report_writer.write(report)

        return result

    def execute_day(
        self,
        state,
        trading_date,
        exit_date,
        previous_ending_value,
        is_rebalance_day,
        signal_date,
    ):

        market_bullish = (
            self.market_filter.is_bullish(
                signal_date
            )
        )

        rankings = (
            self.ranking_service.get_rankings(
                signal_date
            )
        )
        entry_rankings = self.ranking_service.get_entry_rankings(signal_date)
        state = (
            self.portfolio_manager.update(
                state=state,
                rankings=rankings,
                market_bullish=market_bullish,
                rebalance_date=trading_date,
                is_rebalance_day=is_rebalance_day,
                entry_rankings=entry_rankings,
            )
        )
        state.portfolio.rebalance_date = (
            trading_date
        )
        # Daily reports are end-of-day snapshots.  Trading still happens at
        # the open; only the reporting valuation is marked to that session's
        # close.
        period_portfolio = deepcopy(
            state.portfolio
        )
        self.performance_service.accounting.mark_to_market(
            period_portfolio,
            trading_date,
            self.performance_service.execution,
            use_close=True,
        )
        self.performance_service.accounting.rebuild(
            period_portfolio,
            self.portfolio_manager.portfolio_size,
        )

        performance = (
            self.performance_service.calculate(
                portfolio=state.portfolio,
                beginning_value=previous_ending_value,
                entry_signal_date=trading_date,
                exit_signal_date=exit_date,
            )
        )
        period_portfolio.realized_pnl = (
            performance.realized_pnl
        )

        previous_ending_value = (
            performance.ending_value
        )

        return (
            state,
            BacktestPeriod(
                portfolio=period_portfolio,
                performance=performance,
            ),
            previous_ending_value,
        )

    def _process_day(
        self,
        state,
        symbols,
        trading_date,
        exit_date,
        previous_ending_value,
        is_rebalance_day,
        signal_date=None,
    ):
        return self.execute_day(
            state=state,
            trading_date=trading_date,
            exit_date=exit_date,
            previous_ending_value=previous_ending_value,
            is_rebalance_day=is_rebalance_day,
            signal_date=signal_date or trading_date,
        )
