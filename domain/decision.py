from dataclasses import dataclass

from domain.decision_type import DecisionType


@dataclass(slots=True, frozen=True)
class Decision:

    symbol: str

    action: DecisionType

    reason: str

    rank: int

    score: float

    target_weight: float | None = None