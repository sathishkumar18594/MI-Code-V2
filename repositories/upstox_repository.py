"""MI-Code repository adapter for the QM-Book-Code Upstox ISIN store.

The legacy strategy asks repositories for a symbol and expects canonical OHLCV
columns.  QM data is keyed by ISIN, so this adapter resolves current Nifty
constituents to ISINs and normalizes their provider candles without copying or
mutating the source parquet files.
"""
from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from repositories.base_repository import BaseRepository


class UpstoxRepository(BaseRepository):
    TIMELINE_FILE = "nifty500_isin_market_cap_timeline_2016_2026.csv"
    GATE_FILE = "nifty500_corporate_action_backtest_gate.csv"
    ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")

    def __init__(self, data_root: str | Path = "data_v2"):
        self.data_root = Path(data_root)
        self.price_root = self.data_root / "upstox" / "parquet_by_isin"
        self._symbol_to_isin: dict[str, str] | None = None
        self._gate_by_isin: dict[str, str] | None = None
        self._latest_trading_date = None

    def _symbols(self) -> dict[str, str]:
        if self._symbol_to_isin is None:
            mappings: dict[str, str] = {}

            # Historical universe members are absent from today's constituent
            # files. QM's reviewed timeline is the authoritative old-symbol to
            # ISIN identity source for point-in-time backtests.
            timeline_path = (
                self.data_root / "upstox" / "manifests" / self.TIMELINE_FILE
            )
            if timeline_path.exists():
                timeline = pd.read_csv(timeline_path, dtype=str).fillna("")
                if {"symbol", "isin"}.issubset(timeline.columns):
                    identities = timeline.loc[
                        timeline["symbol"].ne("") & timeline["isin"].ne(""),
                        ["symbol", "isin"],
                    ].drop_duplicates()
                    conflicts = identities.groupby("symbol")["isin"].nunique()
                    ambiguous = conflicts[conflicts.gt(1)]
                    if not ambiguous.empty:
                        raise ValueError(
                            "Historical symbols map to multiple ISINs: "
                            + ", ".join(ambiguous.index.tolist())
                        )
                    mappings.update({
                        self._normalize_symbol(symbol): isin.strip().upper()
                        for symbol, isin in identities.itertuples(index=False)
                    })

            # Current files add newly listed constituents that may not yet be
            # present in the dated historical manifest.
            for path in (self.data_root / "universe").glob("*.csv"):
                frame = pd.read_csv(path, dtype=str).fillna("")
                if {"Symbol", "ISIN Code"}.issubset(frame.columns):
                    mappings.update({
                        self._normalize_symbol(symbol): isin.strip().upper()
                        for symbol, isin in zip(frame["Symbol"], frame["ISIN Code"])
                        if symbol and isin
                    })
            self._symbol_to_isin = mappings
        return self._symbol_to_isin

    def _gates(self) -> dict[str, str]:
        if self._gate_by_isin is None:
            gate_path = self.data_root / "upstox" / "manifests" / self.GATE_FILE
            if not gate_path.exists():
                self._gate_by_isin = {}
            else:
                frame = pd.read_csv(gate_path, dtype=str).fillna("")
                self._gate_by_isin = {
                    isin.strip().upper(): gate.strip()
                    for isin, gate in zip(frame["isin"], frame["backtest_gate"])
                    if isin
                }
        return self._gate_by_isin

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol).strip().upper()

    def resolve_isin(self, symbol: str) -> str | None:
        normalized = self._normalize_symbol(symbol)
        if self.ISIN_PATTERN.fullmatch(normalized):
            return normalized
        return self._symbols().get(normalized)

    def availability(self, symbol: str) -> dict[str, str]:
        """Explain whether a symbol is admitted to an MI-Code backtest."""
        isin = self.resolve_isin(symbol)
        if not isin:
            return {"symbol": symbol, "isin": "", "status": "UNRESOLVED_SYMBOL"}

        gate = self._gates().get(isin, "")
        if not gate:
            return {"symbol": symbol, "isin": isin, "status": "NO_BACKTEST_GATE"}
        if not gate.startswith("PASS_"):
            return {"symbol": symbol, "isin": isin, "status": gate}

        path = self.price_root / f"{isin}.parquet"
        status = "LOADED" if path.exists() else "MISSING_PARQUET"
        return {"symbol": symbol, "isin": isin, "status": status}

    def _path(self, symbol: str) -> Path:
        availability = self.availability(symbol)
        if availability["status"] != "LOADED":
            raise FileNotFoundError(
                f"Upstox data unavailable for {symbol}: "
                f"{availability['status']} (ISIN={availability['isin'] or 'unresolved'})"
            )
        return self.price_root / f"{availability['isin']}.parquet"

    def save(self, symbol: str, df: pd.DataFrame):
        raise RuntimeError("UpstoxRepository is read-only; use the Upstox data sync workflow to refresh data_v2.")

    def load(self, symbol: str) -> pd.DataFrame:
        path = self._path(symbol)
        if not path.exists():
            raise FileNotFoundError(f"No Upstox candle series for {symbol}: {path}")
        frame = pd.read_parquet(path).rename(columns={
            "date": "Date", "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        frame = frame[[column for column in required if column in frame]].copy()
        frame["Date"] = pd.to_datetime(frame["Date"])
        return frame.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)

    def exists(self, symbol: str) -> bool:
        return self.availability(symbol)["status"] == "LOADED"

    def last_date(self, symbol: str):
        return pd.Timestamp(self.load(symbol)["Date"].max()).normalize()

    def latest_trading_date(self):
        if self._latest_trading_date is None:
            dates = []
            for path in self.price_root.glob("*.parquet"):
                try:
                    dates.append(pd.Timestamp(pd.read_parquet(path, columns=["date"])["date"].max()))
                except (KeyError, ValueError):
                    continue
            self._latest_trading_date = max(dates).normalize() if dates else None
        return self._latest_trading_date

    def trading_calendar(self) -> pd.DataFrame:
        """Return an NSE session calendar derived from a liquid local equity.

        QM's copied store is equity-only. RELIANCE has the full retained
        history and is used solely for exchange-session dates, never as a
        market-trend proxy.
        """
        return self.load("RELIANCE")[["Date"]].copy()
