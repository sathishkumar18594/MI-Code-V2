from dataclasses import dataclass


@dataclass(slots=True)
class AnnualAssetContributionReport:

    year: int
    stock_days: int
    gold_days: int
    cash_days: int
    stock_pnl: float
    gold_pnl: float
    cash_pnl: float
    total_pnl: float
    stock_pnl_share: float
    gold_pnl_share: float
    cash_pnl_share: float
