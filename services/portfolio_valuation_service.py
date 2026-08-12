from models.portfolio import Portfolio


class PortfolioValuationService:

    def update(

        self,

        portfolio: Portfolio,

    ) -> Portfolio:

        invested = 0.0

        unrealized = 0.0

        for holding in portfolio.holdings:

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

        portfolio.invested_value = invested

        portfolio.unrealized_pnl = unrealized

        portfolio.total_value = (

            portfolio.cash

            + invested

        )

        return portfolio