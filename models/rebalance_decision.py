from dataclasses import dataclass

from models.ranking import Ranking
from models.rebalance_action import RebalanceAction


@dataclass(slots=True, frozen=True)
class RebalanceDecision:

    ranking: Ranking

    action: RebalanceAction