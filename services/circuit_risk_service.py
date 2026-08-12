import pandas as pd


class CircuitRiskService:
    """Point-in-time lower-circuit risk screen based on daily OHLC data."""

    def __init__(self, context):
        settings = context.config.get("circuit_filter", {})
        self.enabled = settings.get("enabled", True)
        self.lookback_days = settings.get("lookback_days", 252)
        self.max_consecutive_hits = settings.get("max_consecutive_hits", 10)
        self.price_tolerance = settings.get("price_tolerance", 0.0001)

    def add_risk_columns(self, df):
        result = df.copy().sort_values("Date").reset_index(drop=True)
        previous_close = result["Close"].shift(1)
        locked = (
            (result["Close"] - result["Low"]).abs()
            <= result["Low"].abs() * self.price_tolerance
        ) & (
            (result["High"] - result["Low"]).abs()
            <= result["Low"].abs() * self.price_tolerance
        )
        lower_circuit_like = (locked & (result["Close"] < previous_close)).fillna(False)
        groups = (~lower_circuit_like).cumsum()
        streak = lower_circuit_like.groupby(groups).cumsum()
        result["max_lower_circuit_streak"] = (
            streak.rolling(self.lookback_days, min_periods=1).max().astype(int)
        )
        return result

    def filter(self, universe):
        if not self.enabled or universe.empty:
            return universe
        return universe[
            universe["max_lower_circuit_streak"] < self.max_consecutive_hits
        ].copy()
