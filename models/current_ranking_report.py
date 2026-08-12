

from dataclasses import dataclass
from datetime import datetime

from models.ranking import Ranking


@dataclass(slots=True)
class CurrentRankingReport:

    trading_date: datetime

    rankings: list[Ranking]

    enabled_factors: list[str]