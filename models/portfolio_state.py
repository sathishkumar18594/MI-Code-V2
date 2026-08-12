from dataclasses import dataclass, field

from models.portfolio import Portfolio


@dataclass(slots=True)
class PortfolioState:

    portfolio: Portfolio | None = None

    invested: bool = False

    cash: float = 1.0