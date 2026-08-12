from dataclasses import dataclass


@dataclass(slots=True)
class AssetClassPerformanceReport:

    asset_class: str
    active_trading_days: int
    active_years: float
    total_return: float
    cagr: float
