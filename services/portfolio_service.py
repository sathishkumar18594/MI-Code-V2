
from application.app_context import AppContext

from services.execution_price_service import ExecutionPriceService

from models.portfolio import Portfolio
from models.portfolio_position import (
    PortfolioPosition,
)


class PortfolioService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        strategy = (
            context.config["strategy"]
        )

        self.portfolio_size = (
            strategy["portfolio_size"]
        )

        self.execution = ExecutionPriceService(context)

    def build(
        self,
        rankings,
        rebalance_date,
    ):

        selected = rankings[
            : self.portfolio_size
        ]

        if not selected:
            return Portfolio(
                rebalance_date=rebalance_date,
                holdings=[],
                cash=0.0,
                available_cash=0.0,
                is_invested=False,
            )

        weight = (
            1 / len(selected)
        )

        holdings = []

        for ranking in selected:
            execution = self.execution.execution_price(ranking.stock.symbol, rebalance_date)
            holdings.append(
                PortfolioPosition(
                    symbol=ranking.stock.symbol,
                    entry_date=execution.date,
                    entry_price=execution.price,
                    quantity=0.0,
                    current_price=execution.price,
                    weight=weight,
                    rank=ranking.rank,
                    score=ranking.stock.score,
                    cost_value=0.0,
                    market_value=0.0,
                )
            )

        return Portfolio(
            rebalance_date=rebalance_date,
            holdings=holdings,
            cash=0.0,
            available_cash=0.0,
            is_invested=bool(holdings),
        )