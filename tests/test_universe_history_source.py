from pathlib import Path

import pandas as pd

from services.universe_service import UniverseService


def write_history(path: Path, symbol: str):
    pd.DataFrame([{
        "effective_date": "2021-03-31",
        "symbols": symbol,
    }]).to_csv(path, index=False)


def test_official_history_takes_precedence(tmp_path):
    service = UniverseService()
    service.history_folder = tmp_path
    write_history(tmp_path / "nifty500_history.csv", "LEGACY")
    official = tmp_path / "nifty500_official_history.csv"
    write_history(official, "OFFICIAL")

    assert service.history_file("NIFTY500") == official
    assert service.get_universe_as_of("nifty500", "2022-01-01") == ["OFFICIAL"]


def test_generic_history_remains_fallback_for_other_universes(tmp_path):
    service = UniverseService()
    service.history_folder = tmp_path
    generic = tmp_path / "nifty100_history.csv"
    write_history(generic, "GENERIC")

    assert service.history_file("NIFTY100") == generic
    assert service.get_universe_as_of("nifty100", "2022-01-01") == ["GENERIC"]

