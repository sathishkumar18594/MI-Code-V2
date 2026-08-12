from models.portfolio import Portfolio


class PortfolioAccountingService:

    def mark_to_market(
        self,
        portfolio: Portfolio,
        valuation_date,
        execution_service,
        use_close=False,
    ):

        for holding in portfolio.holdings:
            if use_close:
                execution = execution_service.closing_price(
                    symbol=holding.symbol,
                    signal_date=valuation_date,
                )
            else:
                execution = execution_service.execution_price(
                    symbol=holding.symbol,
                    signal_date=valuation_date,
                )

            holding.current_price = execution.price
            holding.market_value = (
                holding.quantity * holding.current_price
            )
            holding.unrealized_pnl = (
                holding.market_value - holding.cost_value
            )

    def rebuild(
        self,
        portfolio: Portfolio,
        portfolio_size: int,
    ) -> Portfolio:

        portfolio.invested_value = sum(
            holding.market_value
            for holding in portfolio.holdings
        )

        portfolio.unrealized_pnl = sum(
            holding.unrealized_pnl
            for holding in portfolio.holdings
        )

        portfolio.realized_pnl = sum(
            trade.net_realized_pnl
            for trade in portfolio.trades
        )

        # Lifetime unrealized and realized P&L are snapshot values.
        # Period attribution is calculated later by PerformanceService.

        portfolio.buy_transaction_costs = sum(
            trade.total_charges
            for trade in portfolio.trades
            if trade.entry_date == portfolio.rebalance_date
        )

        portfolio.sell_transaction_costs = sum(
            trade.total_charges
            for trade in portfolio.trades
            if trade.exit_date == portfolio.rebalance_date
        )

        portfolio.transaction_costs = (
            portfolio.buy_transaction_costs
            + portfolio.sell_transaction_costs
        )

        portfolio.total_value = (
            portfolio.cash
            + portfolio.invested_value
        )

        # Accounting identity:
        # total_value == cash + invested_value
        # realized_pnl and unrealized_pnl are informational and do not
        # participate in the total value calculation.

        portfolio.available_cash = portfolio.cash

        portfolio.is_invested = bool(
            portfolio.holdings
        )

        self.validate(
            portfolio,
            portfolio_size,
        )

        return portfolio

    def validate(
        self,
        portfolio: Portfolio,
        portfolio_size: int,
    ):

        assert portfolio.cash >= 0.0

        assert portfolio.invested_value >= 0.0

        assert portfolio.total_value >= 0.0

        assert len(
            portfolio.holdings
        ) <= portfolio_size

        expected_total = (
            portfolio.cash
            + portfolio.invested_value
        )

        assert abs(
            portfolio.total_value
            - expected_total
        ) < 0.01

        for holding in portfolio.holdings:

            assert holding.quantity >= 0.0

            assert holding.cost_value >= 0.0

            assert holding.market_value >= 0.0

            assert holding.current_price >= 0.0

    def debug(
        self,
        portfolio: Portfolio,
        beginning_value,
        entry_signal_date,
        exit_signal_date,
    ):

        print("\n================ PERFORMANCE CHECK ================")
        print(f"Entry Date      : {entry_signal_date}")
        print(f"Exit Date       : {exit_signal_date}")
        print(f"Beginning Value : {beginning_value:,.2f}")

        for holding in portfolio.holdings:
            print(
                f"{holding.symbol:12} "
                f"Qty={holding.quantity:.4f} "
                f"Cost={holding.cost_value:,.2f} "
                f"MV={holding.market_value:,.2f} "
                f"UPNL={holding.unrealized_pnl:,.2f}"
            )

        print(f"Cash            : {portfolio.cash:,.2f}")
        print(f"Invested Value  : {portfolio.invested_value:,.2f}")
        print(f"Ending Value    : {portfolio.total_value:,.2f}")
        print(f"Realized PnL    : {portfolio.realized_pnl:,.2f}")
        print(f"Unrealized PnL  : {portfolio.unrealized_pnl:,.2f}")
        print(f"Holdings        : {len(portfolio.holdings)}")
        print("===================================================\n")
