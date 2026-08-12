"""A separately managed allocation inside the combined portfolio."""

from dataclasses import dataclass, field


@dataclass
class PortfolioSleeve:
    universe: str
    capital: float
    portfolio_size: int
    cash: float
    holdings: list = field(default_factory=list)
    trades: list = field(default_factory=list)

    @property
    def value(self) -> float:
        return self.cash + sum(holding.market_value for holding in self.holdings)
