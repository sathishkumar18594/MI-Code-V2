from copy import deepcopy
from models.portfolio_performance import (
    PortfolioPerformance,
)
from services.execution_price_service import (
    ExecutionPriceService,
)
from services.portfolio_accounting_service import (
    PortfolioAccountingService,
)
from application.app_context import AppContext


class PerformanceService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context
        self.portfolio_size = (
            context.config["strategy"]["portfolio_size"]
        )

        self.execution = (
            ExecutionPriceService(
                context
            )
        )
        self.accounting = (
            PortfolioAccountingService()
        )


    def calculate(
        self,
        portfolio,
        beginning_value,
        entry_signal_date,
        exit_signal_date,
    ):

        # entry_holdings and entry_realized_pnl are no longer needed
        entry_unrealized_pnl = portfolio.unrealized_pnl
        # Create an independent portfolio for exit-date valuation.
        valuation_portfolio = deepcopy(portfolio)

        self.accounting.mark_to_market(
            valuation_portfolio,
            exit_signal_date,
            self.execution,
            use_close=True,
        )

        self.accounting.rebuild(
            valuation_portfolio,
            self.portfolio_size,
        )

        ending_value = valuation_portfolio.total_value
        period_realized_pnl = portfolio.period_realized_pnl

        period_unrealized_pnl = (
            valuation_portfolio.unrealized_pnl
            - entry_unrealized_pnl
        )

        # Lifetime P&L is stored on the portfolio snapshots.
        # Period P&L is derived from the change in lifetime P&L
        # across the performance interval.

        portfolio_return = (
            (ending_value - beginning_value) / beginning_value
            if beginning_value > 0
            else 0.0
        )
        
        debug_enabled = self.context.config.get(
            "debug",
            False,
        )
        self.accounting.validate(
            valuation_portfolio,
            self.portfolio_size,
        )

        if debug_enabled:
            self.accounting.debug(
                valuation_portfolio,
                beginning_value,
                entry_signal_date,
                exit_signal_date,
            )

        if debug_enabled:
            print(
                f"PERFORMANCE | {entry_signal_date.date()} -> {exit_signal_date.date()} | "
                f"Period Realized={period_realized_pnl:,.2f} | "
                f"Period Unrealized={period_unrealized_pnl:,.2f}"
            )

        return PortfolioPerformance(
            start_date=entry_signal_date,
            end_date=exit_signal_date,
            beginning_value=beginning_value,
            ending_value=ending_value,
            period_return=portfolio_return,
            realized_pnl=valuation_portfolio.realized_pnl,
            unrealized_pnl=valuation_portfolio.unrealized_pnl,
            period_realized_pnl=period_realized_pnl,
            period_unrealized_pnl=period_unrealized_pnl,
        )
