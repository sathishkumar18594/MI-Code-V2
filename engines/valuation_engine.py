from domain.account import Account


class ValuationEngine:

    def mark_to_market(
        self,
        account: Account,
    ) -> None:

        invested = 0.0

        unrealized = 0.0

        for holding in account.portfolio.holdings:

            holding.market_value = (

                holding.quantity
                * holding.current_price

            )

            holding.unrealized_pnl = (

                holding.market_value
                - holding.cost_value

            )

            invested += (

                holding.market_value

            )

            unrealized += (

                holding.unrealized_pnl

            )

        account.portfolio.invested_value = invested

        account.portfolio.unrealized_pnl = unrealized

        account.portfolio.total_value = (

            invested
            + account.cash

        )

        account.equity = invested

        account.unrealized_pnl = unrealized

        account.total_value = (

            invested
            + account.cash

        )