from pathlib import Path

import pandas as pd

from repositories.upstox_repository import UpstoxRepository


def _write_candles(path: Path, isin: str):
    output = path / "upstox" / "parquet_by_isin" / f"{isin}.parquet"
    output.parent.mkdir(parents=True)
    pd.DataFrame([{
        "date": "2024-01-02",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1_000,
    }]).to_parquet(output, index=False)


def _write_manifests(path: Path):
    manifests = path / "upstox" / "manifests"
    manifests.mkdir(parents=True)
    pd.DataFrame([
        {"symbol": "OLDNAME", "isin": "INE000A01001"},
        {"symbol": "REVIEWME", "isin": "INE000A01002"},
    ]).to_csv(
        manifests / UpstoxRepository.TIMELINE_FILE,
        index=False,
    )
    pd.DataFrame([
        {
            "isin": "INE000A01001",
            "backtest_gate": "PASS_NO_MATERIAL_ACTION_REPORTED",
        },
        {
            "isin": "INE000A01002",
            "backtest_gate": "REVIEW_MATERIAL_ACTION",
        },
    ]).to_csv(
        manifests / UpstoxRepository.GATE_FILE,
        index=False,
    )


def test_historical_symbol_resolves_to_isin_parquet(tmp_path):
    _write_manifests(tmp_path)
    _write_candles(tmp_path, "INE000A01001")
    repository = UpstoxRepository(tmp_path)

    assert repository.resolve_isin("oldname") == "INE000A01001"
    assert repository.exists("OLDNAME")
    assert repository.load("OLDNAME").columns.tolist() == [
        "Date", "Open", "High", "Low", "Close", "Volume",
    ]


def test_non_pass_gate_is_excluded_even_when_parquet_exists(tmp_path):
    _write_manifests(tmp_path)
    _write_candles(tmp_path, "INE000A01002")
    repository = UpstoxRepository(tmp_path)

    assert not repository.exists("REVIEWME")
    assert repository.availability("REVIEWME")["status"] == "REVIEW_MATERIAL_ACTION"


def test_unresolved_symbol_does_not_fall_back_to_symbol_filename(tmp_path):
    _write_manifests(tmp_path)
    repository = UpstoxRepository(tmp_path)

    assert not repository.exists("UNKNOWN")
    assert repository.availability("UNKNOWN")["status"] == "UNRESOLVED_SYMBOL"
