from domain.account import Account
from domain.decision import Decision
from domain.decision_type import DecisionType
from models.sell_reason import SellReason

from engines.execution_engine import ExecutionEngine


class TradeEngine:

    def __init__(
        self,
        execution_engine: ExecutionEngine,
    ):

        self.execution_engine = (
            execution_engine
        )

    def execute(

        self,

        account: Account,

        decisions: list[Decision],

        rebalance_date,

    ) -> None:

        #
        # Execute sells first.
        #
        for decision in decisions:

            if decision.action != DecisionType.SELL:
                continue

            self.execute_sell(

                account,

                decision,

                rebalance_date,

            )

        #
        # Execute buys afterwards.
        #
        for decision in decisions:

            if decision.action != DecisionType.BUY:
                continue

            self.execute_buy(

                account,

                decision,

                rebalance_date,

            )