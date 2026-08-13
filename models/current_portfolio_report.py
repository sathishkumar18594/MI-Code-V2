from dataclasses import dataclass

from models.portfolio import Portfolio


@dataclass(slots=True)
class CurrentPortfolioReport:

    trading_date: object
    market_data_date: object
    portfolio: Portfolio
    rank_lookup: dict
