from dataclasses import dataclass

from models.portfolio_position import PortfolioPosition
from models.rebalance_decision import RebalanceDecision


@dataclass(slots=True, frozen=True)
class RebalanceResult:

    decisions: list[RebalanceDecision]

    portfolio: list[PortfolioPosition]