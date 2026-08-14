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
        self.minimum_market_cap_crore_by_year = {
            int(year): float(minimum)
            for year, minimum in settings.get(
                "min_market_cap_crore_by_year", {}
            ).items()
        }
        self.point_in_time_overrides = {
            self._normalise_symbol(symbol): {
                "as_of_date": pd.Timestamp(details["as_of_date"]).normalize(),
                "market_cap_crore": float(details["market_cap_crore"]),
            }
            for symbol, details in settings.get(
                "point_in_time_overrides", {}
            ).items()
        }
        self.data_file = Path(settings.get("data_file", self.DEFAULT_FILE))
        self.history_by_symbol = self._load_history() if self.enabled else {}
        self.industry_by_symbol = self._build_industry_history()
        self.current_industry_by_symbol = self._load_current_industries()

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

    def _build_industry_history(self) -> dict[str, pd.DataFrame]:
        histories = {}
        for symbol, frame in self.history_by_symbol.items():
            if not {"industry", "industry_as_of_date"}.issubset(frame.columns):
                continue
            industry = frame[["industry_as_of_date", "industry"]].copy()
            industry["industry_as_of_date"] = pd.to_datetime(
                industry["industry_as_of_date"], errors="coerce"
            )
            industry["industry"] = industry["industry"].fillna("").astype(str).str.strip()
            industry = industry.dropna(subset=["industry_as_of_date"])
            industry = industry[industry["industry"].ne("")]
            if not industry.empty:
                histories[symbol] = industry.sort_values(
                    "industry_as_of_date"
                ).drop_duplicates("industry_as_of_date", keep="last").reset_index(drop=True)
        return histories

    def _load_current_industries(self) -> dict[str, str]:
        if not self.enabled:
            return {}
        data_root = next(
            (parent for parent in self.data_file.parents if parent.name == "data_v2"),
            Path("data_v2"),
        )
        universe_file = data_root / "universe" / "nifty500.csv"
        if not universe_file.exists():
            return {}
        universe = pd.read_csv(universe_file, dtype=str).fillna("")
        if not {"Symbol", "Industry"}.issubset(universe.columns):
            return {}
        return {
            self._normalise_symbol(symbol): industry.strip()
            for symbol, industry in universe[["Symbol", "Industry"]].itertuples(index=False)
            if symbol.strip() and industry.strip()
        }

    def market_cap_as_of(self, symbol: str, date) -> float | None:
        if not self.enabled:
            return None
        normalized_symbol = self._normalise_symbol(symbol)
        date = pd.Timestamp(date).normalize()
        override = self.point_in_time_overrides.get(normalized_symbol)
        history = self.history_by_symbol.get(normalized_symbol)
        index = (
            history["as_of_date"].searchsorted(date, side="right") - 1
            if history is not None and not history.empty
            else -1
        )
        if (
            override is not None
            and override["as_of_date"] <= date
            and (
                index < 0
                or override["as_of_date"] >= history.iloc[index]["as_of_date"]
            )
        ):
            return override["market_cap_crore"]
        if index < 0:
            return None
        return float(
            history.iloc[index]["nse_6m_avg_total_market_cap_crore"]
        )

    def industry_as_of(self, symbol: str, date) -> str | None:
        if not self.enabled:
            return None
        normalized_symbol = self._normalise_symbol(symbol)
        history = self.industry_by_symbol.get(normalized_symbol)
        if history is None or history.empty:
            return self.current_industry_by_symbol.get(normalized_symbol)
        date = pd.Timestamp(date).normalize()
        index = history["industry_as_of_date"].searchsorted(date, side="right") - 1
        if index < 0:
            return self.current_industry_by_symbol.get(normalized_symbol)
        return str(history.iloc[index]["industry"])

    def _normalise_symbol(self, symbol: str) -> str:
        symbol = "".join(str(symbol).upper().split())
        return self.SYMBOL_ALIASES.get(symbol, symbol)

    def minimum_for_date(self, date) -> float:
        """Return the configured threshold in force on the signal date."""
        if date is None or not self.minimum_market_cap_crore_by_year:
            return self.minimum_market_cap_crore
        year = pd.Timestamp(date).year
        effective_years = [
            configured_year
            for configured_year in self.minimum_market_cap_crore_by_year
            if configured_year <= year
        ]
        if not effective_years:
            return self.minimum_market_cap_crore
        return self.minimum_market_cap_crore_by_year[max(effective_years)]

    def filter(self, universe: pd.DataFrame, as_of_date=None) -> pd.DataFrame:
        if not self.enabled:
            return universe.copy()
        minimum = self.minimum_for_date(as_of_date)
        return universe[
            universe["market_cap_crore"].notna()
            & (universe["market_cap_crore"] > minimum)
        ].copy()
