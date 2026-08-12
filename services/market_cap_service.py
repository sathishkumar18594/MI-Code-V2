from pathlib import Path

import pandas as pd


class MarketCapService:
    """Point-in-time entry screen using published historical market caps."""

    DEFAULT_FILE = "data_v2/upstox/manifests/nifty500_isin_market_cap_timeline_2016_2026.csv"
    SYMBOL_ALIASES = {
        "JUBLINGRY": "JUBLFOOD",
        "ORACLE": "OFSS",
        "TVSMNCRPS": "TVSHLTD",
    }

    def __init__(self, context):
        settings = context.config.get("market_cap_filter", {})
        self.enabled = settings.get("enabled", False)
        self.minimum_market_cap_crore = float(
            settings.get("min_market_cap_crore", 0.0)
        )
        self.data_file = Path(settings.get("data_file", self.DEFAULT_FILE))
        self.history_by_symbol = self._load_history() if self.enabled else {}

    def _load_history(self) -> dict[str, pd.DataFrame]:
        if not self.data_file.exists():
            raise FileNotFoundError(
                f"Market-cap filter is enabled but {self.data_file} does not exist"
            )
        data = pd.read_csv(self.data_file)
        # QM's provider manifest is the authoritative V2 source.  Normalize
        # it to the legacy service's point-in-time market-cap contract.
        if "market_cap_as_of_date" in data.columns:
            data = data.rename(columns={
                "market_cap_as_of_date": "as_of_date",
                "market_cap_crore": "nse_6m_avg_total_market_cap_crore",
            })
        data["as_of_date"] = pd.to_datetime(data["as_of_date"])
        required = {
            "as_of_date",
            "symbol",
            "nse_6m_avg_total_market_cap_crore",
        }
        missing = required - set(data.columns)
        if missing:
            raise ValueError(
                f"Market-cap data is missing columns: {sorted(missing)}"
            )
        data["symbol"] = data["symbol"].map(self._normalise_symbol)
        data["nse_6m_avg_total_market_cap_crore"] = pd.to_numeric(
            data["nse_6m_avg_total_market_cap_crore"],
            errors="coerce",
        )
        data = data.dropna(
            subset=["as_of_date", "symbol", "nse_6m_avg_total_market_cap_crore"]
        )
        return {
            symbol: frame.sort_values("as_of_date").reset_index(drop=True)
            for symbol, frame in data.groupby("symbol", sort=False)
        }

    def market_cap_as_of(self, symbol: str, date) -> float | None:
        if not self.enabled:
            return None
        history = self.history_by_symbol.get(self._normalise_symbol(symbol))
        if history is None or history.empty:
            return None
        date = pd.Timestamp(date).normalize()
        index = history["as_of_date"].searchsorted(date, side="right") - 1
        if index < 0:
            return None
        return float(
            history.iloc[index]["nse_6m_avg_total_market_cap_crore"]
        )

    def _normalise_symbol(self, symbol: str) -> str:
        symbol = "".join(str(symbol).upper().split())
        return self.SYMBOL_ALIASES.get(symbol, symbol)

    def filter(self, universe: pd.DataFrame) -> pd.DataFrame:
        if not self.enabled:
            return universe.copy()
        return universe[
            universe["market_cap_crore"].notna()
            & (universe["market_cap_crore"] > self.minimum_market_cap_crore)
        ].copy()
