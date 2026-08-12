from dataclasses import dataclass

from models.stock_snapshot import StockSnapshot


@dataclass(slots=True, frozen=True)
class Ranking:

    rank: int

    stock: StockSnapshot

    score: float
    factor_values: dict[str, float]