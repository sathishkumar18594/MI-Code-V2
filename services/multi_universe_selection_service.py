"""Rank and select the sleeves of the combined multi-index portfolio."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from application.app_context import AppContext
from services.ranking_service import RankingService
from services.universe_service import UniverseService


@dataclass(frozen=True)
class SleeveSelection:
    universe: str
    capital: float
    portfolio_size: int
    rankings: list


class MultiUniverseSelectionService:
    """Produces unique entries while preserving each sleeve's own ranks.

    Earlier sleeves have priority.  A symbol selected by an earlier sleeve is
    skipped by later sleeves, which then continue down their own ranking.
    """

    def __init__(self, context: AppContext):
        self.context = context
        self.universe_service = UniverseService()
        self.ranking_service = RankingService(context)
        self.sleeves = yaml.safe_load(
            Path("config/multi_universe_portfolio.yaml").read_text()
        )["sleeves"]

    def select(self, signal_date) -> list[SleeveSelection]:
        selected_symbols = set()
        selections = []
        for sleeve in self.sleeves:
            universe = sleeve["universe"].lower()
            symbols = self.universe_service.get_universe_as_of(
                universe,
                signal_date,
            )
            rankings = self.ranking_service.rank(
                symbols,
                signal_date,
            )
            unique_rankings = []
            for ranking in rankings:
                if ranking.stock.symbol in selected_symbols:
                    continue
                unique_rankings.append(ranking)
                selected_symbols.add(ranking.stock.symbol)
                if len(unique_rankings) == sleeve["portfolio_size"]:
                    break
            selections.append(SleeveSelection(
                universe=sleeve["universe"],
                capital=float(sleeve["capital"]),
                portfolio_size=int(sleeve["portfolio_size"]),
                rankings=unique_rankings,
            ))
        return selections
