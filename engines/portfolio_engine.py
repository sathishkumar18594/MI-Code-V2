from datetime import datetime

from application.app_context import AppContext

from domain.account import Account
from models.portfolio import Portfolio


class PortfolioEngine:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        config = context.config

        portfolio = config["portfolio"]

        self.initial_capital = (
            portfolio["initial_capital"]
        )

    def create_account(
        self,
    ) -> Account:

        portfolio = Portfolio(
            rebalance_date=datetime.min,
        )

        return Account(

            initial_capital=self.initial_capital,

            cash=self.initial_capital,

            portfolio=portfolio,

            equity=0.0,

            realized_pnl=0.0,

            unrealized_pnl=0.0,

            total_value=self.initial_capital,
        )

    def process_rebalance(

        self,

        account: Account,

        rankings,

        market_bullish,

        rebalance_date,

    ) -> Account:

        #
        # TODO
        #
        # 1 Update prices
        # 2 Value holdings
        # 3 Market SELL?
        # 4 Rank exits
        # 5 Buy replacements
        # 6 Create snapshot
        #

        return account