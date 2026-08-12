"""Read-only historical data layer for the standalone combined portfolio."""

from pathlib import Path

import pandas as pd
import yaml

from indicators.supertrend_indicator import SupertrendIndicator
from services.ranking_service import RankingService
from services.universe_service import UniverseService
from utils.timeframe_converter import TimeframeConverter


class MultiUniverseDataService:
    """Caches ranks and market regimes separately for every index sleeve."""

    def __init__(self, context, config=None):
        self.context = context
        self.universe_service = UniverseService()
        config = config or yaml.safe_load(
            Path("config/multi_universe_portfolio.yaml").read_text()
        )
        self.config = config
        self.sleeves = self.config["sleeves"]
        self.rankers = {}
        self.market_data = {}
        self.sector_scores = {}

    def build(self, trading_dates):
        """Build once before the standalone backtest; never mutates the engine."""
        dates = [pd.Timestamp(date).normalize() for date in trading_dates]
        sleeve_universes = {}
        all_symbols = set()
        for sleeve in self.sleeves:
            universe = sleeve["universe"]
            key = universe.lower()
            symbols_by_date = {
                date: self.universe_service.get_universe_as_of(key, date)
                for date in dates
            }
            sleeve_universes[universe] = symbols_by_date
            all_symbols.update({
                symbol
                for symbols in symbols_by_date.values()
                for symbol in symbols
            })
        # Build indicators once for the union of all sector constituents.
        shared_ranker = RankingService(self.context)
        shared_ranker._build_dataframe_cache(sorted(all_symbols))
        shared_frames = shared_ranker.dataframes
        for sleeve in self.sleeves:
            universe = sleeve["universe"]
            symbols_by_date = sleeve_universes[universe]
            ranker = RankingService(self.context)
            ranker.build_cache(
                symbols=[],
                trading_dates=dates,
                symbols_by_date=symbols_by_date,
                dataframe_cache=shared_frames,
                lazy=True,
                rank_before_filters=(
                    self.config.get("sector_rotation", {}).get("ranking_scope")
                    == "UNIVERSE_BEFORE_FILTERS"
                ),
                apply_market_cap_filter=self.config.get(
                    "sector_rotation", {}
                ).get("market_cap_filter_enabled", True),
            )
            self.rankers[universe] = ranker
            self.market_data[universe] = self._market_regime(sleeve)
        if self.config.get("sector_rotation", {}).get("selection_mode") == "TOP_RANKED_BULLISH":
            self._build_sector_scores()

    def _build_sector_scores(self):
        closes = pd.concat({
            sleeve["universe"]: self.context.index_repository.load(sleeve.get("index_name", sleeve["universe"])).set_index("Date")["Close"]
            for sleeve in self.sleeves
        }, axis=1).sort_index().resample("W-FRI").last().ffill()
        factors = {
            "r6": closes.pct_change(26),
            "r3": closes.pct_change(13),
            "r1": closes.pct_change(4),
        }
        settings = self.config.get("sector_rotation", {}).get("sector_score", {})
        weights = {
            "r6": float(settings.get("return_6m_weight", 0.50)),
            "r3": float(settings.get("return_3m_weight", 0.30)),
            "r1": float(settings.get("return_1m_weight", 0.20)),
        }
        for date in closes.index:
            eligible = [u for u in closes.columns if self.is_bullish(u, date)]
            frame = pd.DataFrame({key: value.loc[date, eligible] for key, value in factors.items()})
            # The requested score requires all three completed lookbacks.
            frame = frame.dropna(subset=list(weights))
            if frame.empty:
                self.sector_scores[pd.Timestamp(date).normalize()] = []
                continue
            frame["score"] = sum(frame[factor] * weight for factor, weight in weights.items())
            self.sector_scores[pd.Timestamp(date).normalize()] = frame.sort_values("score", ascending=False).index.tolist()

    def sector_rankings(self, date):
        eligible = [key for key in self.sector_scores if key <= pd.Timestamp(date).normalize()]
        return self.sector_scores[max(eligible)] if eligible else []

    def rankings(self, universe, date, entry=False):
        ranker = self.rankers[universe]
        return (
            ranker.get_entry_rankings(date)
            if entry
            else ranker.get_rankings(date)
        )

    def is_bullish(self, universe, date):
        data = self.market_data[universe]
        completed = data[data["Date"] <= pd.Timestamp(date)]
        return bool(not completed.empty and completed.iloc[-1]["trend"] == 1)

    def circuit_risk(self, universe, symbol, date):
        frame = self.rankers[universe].dataframes.get(symbol)
        if frame is None or frame.empty:
            return {}
        index = frame["Date"].searchsorted(pd.Timestamp(date), side="right") - 1
        if index < 0:
            return {}
        row = frame.iloc[index]
        lookback = self.rankers[universe].circuit_risk_service.lookback_days
        start = frame.iloc[max(0, index - lookback + 1)]["Date"]
        return {
            "lookback_start_date": start,
            "as_of_date": row["Date"],
            "max_lower_circuit_streak": int(row["max_lower_circuit_streak"]),
            "filter_threshold": self.rankers[
                universe
            ].circuit_risk_service.max_consecutive_hits,
        }

    def entry_filter_reason(self, universe, symbol, date):
        """Identify the point-in-time entry screen that excluded a stock."""
        risk = self.circuit_risk(universe, symbol, date)
        if risk.get("max_lower_circuit_streak", 0) >= risk.get(
            "filter_threshold", float("inf")
        ):
            return "LOWER_CIRCUIT_FILTER"
        ranker = self.rankers[universe]
        market_cap = ranker.market_cap_service.market_cap_as_of(symbol, date)
        if (
            self.config.get("sector_rotation", {}).get(
                "market_cap_filter_enabled", True
            )
            and ranker.market_cap_service.enabled
            and (
                market_cap is None
                or market_cap <= ranker.market_cap_service.minimum_market_cap_crore
            )
        ):
            return "MARKET_CAP_FILTER"
        return "ENTRY_FILTER"

    def _market_regime(self, sleeve):
        """Same weekly (1, 2.5) logic, calculated from this sleeve's index."""
        # The universe identifier and its benchmark file are usually the same
        # for broad indices.  Sector sleeves deliberately use their own
        # benchmark name, so they can have an independent market regime.
        index_name = sleeve.get("index_name", sleeve["universe"])
        data = self.context.index_repository.load(index_name).copy()
        regime = self.config.get("market_regime", {})
        timeframe = regime.get("timeframe", "WEEKLY")
        weekly = TimeframeConverter.convert(data, timeframe)
        return SupertrendIndicator().execute(
            weekly,
            period=int(regime.get("supertrend_period", 1)),
            multiplier=float(regime.get("supertrend_multiplier", 2.5)),
        )
