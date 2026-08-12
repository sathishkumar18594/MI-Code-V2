from models.portfolio_position import PortfolioPosition
from models.ranking import Ranking
from models.rebalance_action import RebalanceAction
from models.rebalance_decision import RebalanceDecision
from models.rebalance_result import RebalanceResult


class RebalanceEngine:

    def rebalance(
        self,
        current_portfolio: list[PortfolioPosition],
        rankings: list[Ranking],
        portfolio_size: int,
        hold_threshold: int,
    ) -> RebalanceResult:

        decisions: list[RebalanceDecision] = []

        #
        # Build lookup tables
        #

        rank_lookup = {
            ranking.stock.symbol: ranking
            for ranking in rankings
        }

        current_symbols = {
            position.stock.symbol
            for position in current_portfolio
        }

        #
        # Keep holdings inside hold threshold
        #

        new_portfolio: list[PortfolioPosition] = []

        for position in current_portfolio:

            symbol = position.stock.symbol

            ranking = rank_lookup.get(symbol)

            if (
                ranking is not None
                and ranking.rank <= hold_threshold
            ):

                new_portfolio.append(position)

                decisions.append(

                    RebalanceDecision(
                        ranking=ranking,
                        action=RebalanceAction.HOLD,
                    )

                )

            elif ranking is not None:

                decisions.append(

                    RebalanceDecision(
                        ranking=ranking,
                        action=RebalanceAction.SELL,
                    )

                )

        #
        # Fill remaining slots
        #

        portfolio_symbols = {
            position.stock.symbol
            for position in new_portfolio
        }

        weight = 1 / portfolio_size

        for ranking in rankings:

            if len(new_portfolio) >= portfolio_size:
                break

            symbol = ranking.stock.symbol

            if symbol in portfolio_symbols:
                continue

            new_position = PortfolioPosition(
                stock=ranking.stock,
                weight=weight,
            )

            new_portfolio.append(new_position)

            portfolio_symbols.add(symbol)

            if symbol not in current_symbols:

                decisions.append(

                    RebalanceDecision(
                        ranking=ranking,
                        action=RebalanceAction.BUY,
                    )

                )

        return RebalanceResult(
            decisions=decisions,
            portfolio=new_portfolio,
        )